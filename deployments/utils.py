# deployments/utils.py
import docker
from docker.errors import DockerException, APIError, ContainerError, NotFound
from .models import Deployment, DeploymentContainerEnvVar, DeploymentContainer
from projects.models import ProjectContainer
from plans.models import Plan
import socket
import logging
import os

logger = logging.getLogger(__name__)


# ---------------- Helpers ----------------
def get_free_port(start=8000, end=9000):
    """العثور على أول منفذ متاح في النطاق المحدد"""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise RuntimeError("No free ports available in range 8000-9000")


def run_container(client, **kwargs):
    try:
        return client.containers.run(**kwargs)
    except APIError as e:
        logger.error(f"Failed to run container {kwargs.get('name')}: {str(e)}")
        return None


def ensure_network(client, name="deploy_network"):
    try:
        client.networks.get(name)
    except NotFound:
        client.networks.create(name, driver="bridge")
        logger.info(f"Network {name} created")


def ensure_image(client, image_name):
    try:
        client.images.get(image_name)
    except docker.errors.ImageNotFound:
        logger.info(f"Pulling image {image_name}")
        client.images.pull(image_name)


def remove_container_if_exists(client, name):
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        logger.info(f"Removed old container {name}")
    except NotFound:
        pass


# ---------------- Dedicated containers ----------------
def create_project_db_container(deployment):
    client = docker.from_env()
    container_name = f"{deployment.user.username}{deployment.id}_db"
    db_name = f"db_{deployment.id}"
    db_user = "postgres"
    db_pass = "postgres"

    labels = {"traefik.enable": "false"}  # قاعدة البيانات لا تمر عبر Traefik

    try:
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"DB container {container_name} started successfully")
    except NotFound:
        logger.warning(f"DB container {container_name} not found, creating new one...")
        container = client.containers.run(
            image="postgres:14",
            name=container_name,
            detach=True,
            environment={
                "POSTGRES_DB": db_name,
                "POSTGRES_USER": db_user,
                "POSTGRES_PASSWORD": db_pass,
            },
            volumes={
                f"db_data_{deployment.id}": {"bind": "/var/lib/postgresql/data", "mode": "rw"}
            },
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"},
            labels=labels,
        )
    return container


def create_project_redis_container(deployment):
    client = docker.from_env()
    container_name = f"{deployment.container_name}_redis"

    labels = {"traefik.enable": "false"}  # Redis أيضاً لا يمر عبر Traefik

    try:
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"Redis container {container_name} started successfully")
    except NotFound:
        logger.warning(f"Redis container {container_name} not found, creating new one...")
        container = client.containers.run(
            image="redis:7",
            name=container_name,
            detach=True,
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"},
            labels=labels,
        )
    return container


# ---------------- حساب تقسيم الموارد ----------------
def calculate_resource_limits(deployment):
    plan_ram_mb = float(getattr(deployment.plan, "ram", 512))
    plan_cpu = float(getattr(deployment.plan, "cpu", 0.5))
    containers = list(deployment.containers.all())
    limits = {}

    # تصنيف حسب النوع
    backends = [c for c in containers if c.project_container.type in ("backend", "backfront")]
    frontends = [c for c in containers if c.project_container.type == "frontend"]
    redis_containers = [c for c in containers if c.project_container.type == "redis"]

    total_weight = len(backends)*2 + len(frontends)*1 + len(redis_containers)*0.5

    for c in containers:
        if c.project_container.type in ("backend", "backfront"):
            weight = 2
        elif c.project_container.type == "frontend":
            weight = 1
        else:  # redis أو غيره
            weight = 0.5

        ram_for_container = int(plan_ram_mb * (weight/total_weight))
        cpu_for_container = plan_cpu * (weight/total_weight)
        limits[c.container_name] = {
            "mem": f"{ram_for_container}m",
            "cpu": int(cpu_for_container * 100000)
        }

    return limits

def expand_env(value, fixed_env):
    """توسيع المتغيرات داخل string أو list أو dict بشكل recursive"""
    if isinstance(value, str):
        try:
            return str(eval(f'f"""{value}"""', {}, fixed_env))
        except Exception:
            return value
    elif isinstance(value, list):
        return [expand_env(v, fixed_env) for v in value]
    elif isinstance(value, dict):
        return {k: expand_env(v, fixed_env) for k, v in value.items()}
    else:
        return value

# ---------------- Project containers ----------------
def create_project_container(deployment, container: DeploymentContainer):
    client = docker.from_env()
    pc = container.project_container
    container_name = container.container_name
    avalible_port = get_free_port()
    ensure_network(client)

    db_container_name = f"{deployment.user.username}{deployment.id}_db"
    plan = deployment.plan
    image_name = pc.docker_image_name
    domain = container.domain



    resource_limits = calculate_resource_limits(deployment)
    mem_limit = resource_limits.get(container_name, {}).get("mem", f"{getattr(plan, 'ram', 512)}m")
    cpu_quota = resource_limits.get(container_name, {}).get("cpu", int(getattr(plan, "cpu", 0.5)*100000))

    # ---------------- بيئة الحاوية ----------------
    db_name = f"db_{deployment.id}"
    db_user = "postgres"
    db_pass = "postgres"

    # قيم ثابتة نريد إضافتها
    env_vars = pc.env_vars or {}
    fixed_env = {
        "deployment": deployment,
        "plan": plan,
        "container": container,

        "this_container_domain": container.domain,
        "frontend_domain":deployment.domain,
        "backfront_domain":deployment.backend_domain,

        "db_name": db_name,
        "db_user": db_user,
        "db_pass": db_pass,
        "db_container_name": db_container_name,
    }

    final_env = {k: expand_env(v, fixed_env) for k, v in env_vars.items()}
    # ---------------- Traefik Labels ----------------
    labels = {}
    if pc.type == "frontend":
        labels = {
            "traefik.enable": "true",
            f"traefik.http.routers.{container_name}.rule": f"Host(`{domain}`)",
            f"traefik.http.routers.{container_name}.entrypoints": "web,websecure",
            f"traefik.http.routers.{container_name}.tls.certresolver": "myresolver",
            f"traefik.http.services.{container_name}.loadbalancer.server.port": str(pc.default_port or 80),
        }
    elif pc.type in ("backend", "backfront"):
        labels = {
            "traefik.enable": "true",
            f"traefik.http.routers.{container_name}.rule": f"Host(`{domain}`)",
            f"traefik.http.routers.{container_name}.entrypoints": "web,websecure",
            f"traefik.http.routers.{container_name}.tls.certresolver": "myresolver",
            f"traefik.http.services.{container_name}.loadbalancer.server.port": str(pc.default_port or 8000),
        }
        final_env.update({
            "DOMAIN": domain,
            "ALLOWED_HOSTS": f"127.0.0.1,localhost,{domain}",
            "DATABASE_URL": f"postgres://{db_user}:{db_pass}@{db_container_name}:5432/{db_name}"
        })
    elif pc.type == "redis":
        labels = {"traefik.enable": "false"}
    
    # ---------------- Volumes ----------------
    volumes = {}
    for vol in (pc.volume or []):
        if isinstance(vol, dict):
            host_path = vol["host"]
            container_path = vol["container"]
            if not container_path.startswith("/"):
                container_path = f"/{container_path}"
            volumes[host_path] = {"bind": container_path, "mode": "rw"}
        else:
            host_path = vol
            container_path = f"/{vol}"
            volumes[host_path] = {"bind": container_path, "mode": "rw"}

    # ---------------- تشغيل أو إنشاء الحاوية ----------------
    try:
        c = client.containers.get(container_name)
        c.start()
        logger.info(f"Project container {container_name} started successfully")
    except NotFound:
        logger.warning(f"Project container {container_name} not found, creating a new one...")
        c = run_container(
            client,
            image=image_name,
            name=container_name,
            labels=labels,
            detach=True,
            mem_limit=mem_limit,
            cpu_quota=cpu_quota,
            volumes=volumes,
            environment=final_env,
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"},
            ports={'8000': avalible_port},
        )

        if c and pc.script_run_after_install:
            for script in pc.script_run_after_install.splitlines():
                script = script.strip()
                if script:
                    try:
                        exec_result = c.exec_run(script.format(container=container))
                        print(f"Executed: {script}\nOutput:\n{exec_result.output.decode()}")
                    except Exception as e:
                        print(f"Failed to run script {script}: {e}")

    return True


def update_deployment(deployment, progress, status):
    deployment.progress = progress
    deployment.status = status
    deployment.save()

# ---------------- Runner ----------------
def run_docker(deployment: Deployment):
    client = docker.from_env()

    # أولاً: DB
    db_ok = create_project_db_container(deployment)
    if not db_ok:
        update_deployment(deployment, 5, 3)
        return False

    # ثانياً: باقي الحاويات
    all_ok = True
    for container in deployment.containers.all():
        try:
            if container.project_container.type == 'redis':
                ok = create_project_redis_container(deployment)
            else:
                ok = create_project_container(deployment, container)
            if not ok:
                logger.error(f"Failed to create container {container.container_name}")
                all_ok = False
        except Exception as e:
            logger.error(f"Error deploying container {container.container_name}: {e}")
            all_ok = False

    # تحديث حالة Deployment
    if all_ok:
        update_deployment(deployment, 4, 2)  # Completed / Running
        logger.info(f"Deployment succeeded: {deployment}")
        return True
    else:
        update_deployment(deployment, 5, 3)  # Failed
        return False



def delete_container(client, cname):
    if cname:
        try:
            c = client.containers.get(cname)
            c.stop()
            c.remove()
            logger.info(f"Container {cname} removed")
            return True
        except NotFound:
            logger.warning(f"Container {cname} not found")
        except DockerException as e:
            logger.error(f"Failed to remove container {cname}: {e}")

def delete_docker(deployment: Deployment):
    containers = deployment.containers.all()
    client = docker.from_env()
    
    delete_container(client, f"{deployment.user.username}{deployment.id}_db")
    for container in containers:
        cname = container.container_name
        delete_container(client, cname)
    
        volumes = container.project_container.volume
        volumes.append(f"db_data_{deployment.id}")
        for vol in volumes:
            if vol:
                try:
                    v = client.volumes.get(vol)
                    v.remove(force=True)
                    logger.info(f"Volume {vol} removed")
                except NotFound:
                    logger.warning(f"Volume {vol} not found")
                except DockerException as e:
                    logger.error(f"Failed to remove volume {vol}: {e}")
    return True

def rebuild_docker(deployment: Deployment):
    delete_docker(deployment)
    return run_docker(deployment)

def restart_docker_db(deployment: Deployment):
    client = docker.from_env()
    db_container_name = f"{deployment.user.username}{deployment.id}_db"

    try:
        db_container = client.containers.get(db_container_name)
        db_container.restart()
        logger.info(f"Database container {db_container_name} restarted successfully")
    except NotFound:
        create_project_db_container(deployment)
        logger.warning(f"Database container {db_container_name} not found, creating a new one...")
    return True

def restart_docker(deployment: Deployment):
    client = docker.from_env()
    all_ok = True

    # أولاً: إعادة تشغيل قاعدة البيانات
    db_container_name = f"{deployment.user.username}{deployment.id}_db"
    try:
        db_container = client.containers.get(db_container_name)
        db_container.restart()
        logger.info(f"Database container {db_container_name} restarted successfully")
    except NotFound:
        create_project_db_container(deployment)
        logger.warning(f"Database container {db_container_name} not found, creating a new one...")
    except DockerException as e:
        logger.error(f"Failed to restart database container: {e}")
        all_ok = False

    # إعادة تشغيل باقي الحاويات
    for dc in deployment.containers.all():
        cname = dc.container_name
        if not cname:
            logger.error("No container associated with this deployment")
            all_ok = False
            continue
        try:
            container = client.containers.get(cname)
            container.restart()
            logger.info(f"Container {cname} restarted successfully")
        except NotFound:
            create_project_container(deployment, dc)
            logger.warning(f"Container {cname} not found, creating a new one...")
        except DockerException as e:
            logger.error(f"Failed to restart container {cname}: {e}")
            all_ok = False

    deployment.status = 2 if all_ok else 3  # Running أو Failed
    deployment.save()
    return all_ok






def stop_docker(deployment: Deployment):
    client = docker.from_env()
    all_ok = True

    for dc in deployment.containers.all():
        cname = dc.container_name
        if not cname:
            logger.error("No container associated with this deployment")
            all_ok = False
            continue
        try:
            container = client.containers.get(cname)
            container.stop()
            logger.info(f"Container {cname} stopped successfully")
        except NotFound:
            logger.warning(f"Container {cname} not found")
        except DockerException as e:
            logger.error(f"Failed to stop container {cname}: {e}")
            all_ok = False

    # إيقاف قاعدة البيانات
    db_container_name = f"{deployment.user.username}{deployment.id}_db"
    try:
        db_container = client.containers.get(db_container_name)
        db_container.stop()
        logger.info(f"Database container {db_container_name} stopped successfully")
    except NotFound:
        logger.warning(f"Database container {db_container_name} not found")
    except DockerException as e:
        logger.error(f"Failed to stop database container: {e}")
        all_ok = False

    deployment.status = 1  # Stopped
    deployment.save()
    return all_ok


def start_docker(deployment: Deployment):
    client = docker.from_env()

    # تشغيل قاعدة البيانات أولًا
    db_container_name = f"{deployment.user.username}{deployment.id}_db"
    try:
        db_container = client.containers.get(db_container_name)
        db_container.start()
        logger.info(f"Database container {db_container_name} started successfully")
    except NotFound:
        create_project_db_container(deployment)
        logger.warning(f"Database container {db_container_name} not found, creating a new one...")
    except DockerException as e:
        logger.error(f"Failed to start database container: {e}")

    all_ok = True
    for dc in deployment.containers.all():
        cname = dc.container_name
        if not cname:
            logger.error("No container associated with this deployment")
            all_ok = False
            continue
        try:
            container = client.containers.get(cname)
            container.start()
            logger.info(f"Container {cname} started successfully")
        except NotFound:
            create_project_container(deployment, dc)
            logger.warning(f"Container {cname} not found, creating a new one...")
        except DockerException as e:
            logger.error(f"Failed to start container {cname}: {e}")
            all_ok = False

    deployment.status = 2 if all_ok else 3
    deployment.save()
    return all_ok


def get_container_usage(container_name):
    client = docker.from_env()
    usage = {}
    media_path = "/app/media"

    def calculate_cpu_percent(stats):
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - stats["precpu_stats"].get("system_cpu_usage", 0)
        cpu_percent = 0.0
        if system_delta > 0.0 and cpu_delta > 0.0:
            percpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            cpu_percent = (cpu_delta / system_delta) * percpu_count * 100.0
        return cpu_percent

    try:
        # الحصول على حاوية المشروع
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)

        # ---------------- RAM ----------------
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 1)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

        # ---------------- CPU ----------------
        cpu_percent = calculate_cpu_percent(stats)

        # ---------------- Storage (media) ----------------
        try:
            exec_result = container.exec_run(f"du -sb {media_path}")
            storage_media = int(exec_result.output.decode().split()[0])
        except Exception:
            storage_media = 0

        # المجموع النهائي للتخزين
        total_storage = storage_media 

        usage = {
            "memory_usage": mem_usage,
            "memory_limit": mem_limit,
            "memory_percent": round(mem_percent, 2),
            "cpu_percent": round(cpu_percent, 2),
            "storage_media": storage_media,
            "storage_usage": total_storage
        }

    except docker.errors.NotFound:
        usage = {"error": f"Container {container_name} not found"}
    except Exception as e:
        usage = {"error": str(e)}

    return usage

def get_db_container_usage(deployment):
    client = docker.from_env()
    db_container_name = f"{deployment.user.username}{deployment.id}_db"
    # ---------------- Storage (Postgres DB) ----------------
    storage_db = 0
    try:
        db_container = client.containers.get(db_container_name)
        exec_result = db_container.exec_run("du -sb /var/lib/postgresql/data")
        storage_db = int(exec_result.output.decode().split()[0])
    except Exception:
        storage_db = 0
    return {
        "storage_db": storage_db
    }