# deployments/utils.py
import docker
from docker.errors import DockerException, APIError, ContainerError, NotFound
from .models import Deployment, DeploymentEnvVar
from plans.models import Plan
import socket
import logging
import os

logger = logging.getLogger(__name__)

# ---------- Helpers ----------
def get_free_port(start=8000, end=9000):
    """العثور على أول منفذ متاح في النطاق المحدد"""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise RuntimeError("No free ports available in range 8000-9000")


def ensure_traefik_running(client):
    """تشغيل Traefik إذا لم يكن موجود"""
    try:
        client.containers.get("traefik")
        logger.info("Traefik already running")
    except docker.errors.NotFound:
        # إنشاء شبكة deploy_network إذا لم تكن موجودة
        try:
            client.networks.get("deploy_network")
        except docker.errors.NotFound:
            client.networks.create("deploy_network", driver="bridge")
            logger.info("Network 'deploy_network' created")

        traefik_yml = "/opt/traefik/traefik.yml"  # ملف Traefik على Ubuntu
        acme_file = "/opt/traefik/acme.json"
        os.makedirs(os.path.dirname(acme_file), exist_ok=True)
        if not os.path.exists(acme_file):
            open(acme_file, 'a').close()
            os.chmod(acme_file, 0o600)

        client.containers.run(
            "traefik:latest",
            name="traefik",
            detach=True,
            network="deploy_network",
            ports={"80/tcp": 80, "443/tcp": 443},
            volumes={
                traefik_yml: {"bind": "/traefik.yml", "mode": "ro"},
                acme_file: {"bind": "/acme.json", "mode": "rw"},
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"}
            }
        )
        logger.info("Traefik started")


def update_deployment(deployment, progress, status, container_name, port=None):
    deployment.progress = progress
    deployment.status = status
    if port:
        deployment.port = port
    deployment.container_name = container_name
    deployment.save()





def run_container(client, **kwargs):
    try:
        return client.containers.run(**kwargs)
    except APIError as e:
        logger.error(f"Failed to run container: {str(e)}")
        return None
    
def ensure_network(client, name="deploy_network"):
    try:
        client.networks.get(name)
    except NotFound:
        client.networks.create(name, driver="bridge")
        logger.info(f"Network {name} created")

def ensure_volume(client, name):
    try:
        client.volumes.get(name)
    except NotFound:
        client.volumes.create(name=name)
        logger.info(f"Volume {name} created")

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

def ensure_traefik(client, network_name):
    try:
        client.containers.get("traefik")
        logger.info("Traefik already running")
    except NotFound:
        ensure_network(client, network_name)

        traefik_yml = "/opt/traefik/traefik.yml"
        acme_file = "/opt/traefik/acme.json"
        os.makedirs(os.path.dirname(acme_file), exist_ok=True)
        if not os.path.exists(acme_file):
            open(acme_file, 'a').close()
            os.chmod(acme_file, 0o600)

        client.containers.run(
            "traefik:latest",
            name="traefik",
            detach=True,
            network=network_name,
            ports={"8000/tcp": 8000, "8443/tcp": 8443, "8080/tcp": 8080},
            volumes={
                traefik_yml: {"bind": "/traefik.yml", "mode": "ro"},
                acme_file: {"bind": "/acme.json", "mode": "rw"},
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"}
            }
        )
        logger.info("Traefik started")



def create_project_db_container(deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False

    ensure_network(client)

    db_container_name = f"{deployment.container_name}_db"
    volume_db = f"{db_container_name}_data"
    db_name = f"db_{deployment.id}"
    db_user = "postgres"
    db_pass = "postgres"

    try:
        db_container = client.containers.get(db_container_name)
        db_container.start()
        logger.info(f"Database container {db_container_name} started successfully")
    except NotFound:
        logger.warning(f"Database container {db_container_name} not found, creating a new one...")
        run_container(
            client,
            image="postgres:14",
            name=db_container_name,
            detach=True,
            environment={
                "POSTGRES_DB": db_name,
                "POSTGRES_USER": db_user,
                "POSTGRES_PASSWORD": db_pass,
            },
            volumes={volume_db: {"bind": "/var/lib/postgresql/data", "mode": "rw"}},
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"}
        )

    return True

def create_project_container(deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False

    ensure_network(client)

    container_name = deployment.container_name
    db_container_name = f"{container_name}_db"
    plan = deployment.plan
    image_name = deployment.project.docker_image_name
    volume_media = deployment.volume_media
    domain = deployment.domain

    ram_limit = getattr(plan, "ram", 512)
    cpu_limit = getattr(plan, "cpu", 0.5)
    mem_limit = f"{ram_limit}m"
    cpu_quota = int(cpu_limit * 100000)

    db_name = f"db_{deployment.id}"
    db_user = "postgres"
    db_pass = "postgres"

    env_vars = {
        env.var_name.key: env.value
        for env in DeploymentEnvVar.objects.filter(deployment=deployment)
    }

    fixed_env = {
        "USERNAME": deployment.user.username,
        "PLAN": plan.name,
        "PROJECT": deployment.project.name,
        "DATABASE_URL": f"postgres://{db_user}:{db_pass}@{db_container_name}:5432/{db_name}",
        "DOMAIN": domain,
        "ALLOWED_HOSTS": f"localhost,127.0.0.1,{domain}",
        "CSRF_TRUSTED_ORIGINS": f"https://{domain}:8443,https://{domain}"
    }

    final_env = {**fixed_env, **env_vars}
    # ---------- DATABASE ENV VARS ----------
    final_env[deployment.project.db_engine_env_var_name] = 'postgresql'
    final_env[deployment.project.db_name_env_var_name] = db_name
    final_env[deployment.project.db_user_env_var_name] = db_user
    final_env[deployment.project.db_password_env_var_name] = db_pass
    final_env[deployment.project.db_host_env_var_name] = db_container_name
    final_env[deployment.project.db_port_env_var_name] = "5432"


    if deployment.project.has_redis:
        redis_container_name = f"{container_name}_redis"
        final_env[deployment.project.redis_host_env_var_name] = redis_container_name
        final_env[deployment.project.redis_port_env_var_name] = "6379"

    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{container_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.routers.{container_name}.entrypoints": "web,websecure",
        f"traefik.http.routers.{container_name}.tls.certresolver": "myresolver",
        f"traefik.http.services.{container_name}.loadbalancer.server.port": "8000"
    }

    try:
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"Project container {container_name} started successfully")
    except NotFound:
        logger.warning(f"Project container {container_name} not found, creating a new one...")
        container = run_container(
            client,
            image=image_name,
            name=container_name,
            labels=labels,
            detach=True,
            mem_limit=mem_limit,
            cpu_quota=cpu_quota,
            volumes={volume_media: {'bind': '/app/media', 'mode': 'rw'}},
            environment=final_env,
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"}
        )
        if container:
            # جلب السكربتات المراد تشغيلها بعد التثبيت
            scripts = deployment.project.scripts_after_install.splitlines()  # كل سطر سكربت
            for script in scripts:
                script = script.strip()
                if not script:
                    continue  # تجاهل السطور الفارغة
                # استبدال القيم الديناميكية
                script = script.format(deployment=deployment)
                try:
                    exec_result = container.exec_run(script)
                    print(f"Script executed: {script}\nOutput:\n{exec_result.output.decode()}")
                except Exception as e:
                    print(f"Failed to run script {script}: {e}")
    deployment.status = 2
    deployment.save()
    return True


def create_project_frontend_container(deployment):
    client = docker.from_env()
    if not deployment.frontend_container_name:
        logger.error("No frontend container associated with this deployment")
        return False

    ensure_network(client)

    container_name = deployment.frontend_container_name
    image_name = deployment.project.frontend_docker_image_name
    domain = deployment.frontend_domain

    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{container_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.routers.{container_name}.entrypoints": "web,websecure",
        f"traefik.http.routers.{container_name}.tls.certresolver": "myresolver",
        f"traefik.http.services.{container_name}.loadbalancer.server.port": "80"
    }

    try:
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"Frontend container {container_name} started successfully")
    except NotFound:
        logger.warning(f"Frontend container {container_name} not found, creating a new one...")
        run_container(
            client,
            image=image_name,
            name=container_name,
            labels=labels,
            detach=True,
            network="deploy_network",
            restart_policy={"Name": "unless-stopped"}
        )

    return True

def create_project_redis_container(deployment: Deployment):
    try:
        client = docker.from_env()
        container = client.containers.run(
            deployment.project.redis_docker_image_name,
            name=deployment.redis_container_name,
            detach=True,
            restart_policy={"Name": "always"},
            network="deploy_network"
        )
        logger.info(f"Redis container created: {container.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to create Redis container: {str(e)}")
        return False


def run_docker(deployment: Deployment):
    client = docker.from_env()
    container_name = f"{deployment.user.username}_{deployment.project.name}_{deployment.id}".lower()
    deployment.container_name = container_name

    # إذا المشروع عنده frontend
    if deployment.project.has_frontend:
        deployment.frontend_container_name = f"{container_name}_frontend"
        deployment.frontend_domain = f"frontend.{deployment.domain}"

    # إذا المشروع يحتاج Redis
    if deployment.project.has_redis:
        deployment.redis_container_name = f"{container_name}_redis"

    deployment.save()

    # إعداد الشبكة و Traefik
    ensure_traefik(client, network_name="deploy_network")

    # تحميل الصور
    ensure_image(client, deployment.project.docker_image_name)
    if deployment.project.has_frontend and deployment.project.frontend_docker_image_name:
        ensure_image(client, deployment.project.frontend_docker_image_name)
    if deployment.project.has_redis and deployment.project.redis_docker_image_name:
        ensure_image(client, deployment.project.redis_docker_image_name)

    # إزالة الحاويات القديمة
    remove_container_if_exists(client, container_name)
    remove_container_if_exists(client, f"{container_name}_db")
    if deployment.frontend_container_name:
        remove_container_if_exists(client, deployment.frontend_container_name)
    if deployment.redis_container_name:
        remove_container_if_exists(client, deployment.redis_container_name)

    # إنشاء حاوية قاعدة البيانات
    db_success = create_project_db_container(deployment)
    if not db_success:
        update_deployment(deployment, 5, 3, container_name)
        return False

    # إنشاء حاوية Redis إذا مطلوب
    if deployment.project.has_redis:
        redis_success = create_project_redis_container(deployment)
        if not redis_success:
            update_deployment(deployment, 5, 3, container_name)
            return False

    # إنشاء حاوية الـ backend
    app_success = create_project_container(deployment)
    if not app_success:
        update_deployment(deployment, 5, 3, container_name)
        return False

    # إنشاء حاوية الـ frontend إذا مطلوب
    if deployment.project.has_frontend:
        frontend_success = create_project_frontend_container(deployment)
        if not frontend_success:
            update_deployment(deployment, 5, 3, container_name)
            return False

    # تحديث حالة النشر
    update_deployment(deployment, 4, 2, container_name)
    logger.info(f"Deployment succeeded: {container_name}")
    return True



def delete_docker(deployment: Deployment):
    client = docker.from_env()
    for cname in [deployment.container_name, f"{deployment.container_name}_db"]:
        if cname:
            try:
                c = client.containers.get(cname)
                c.stop()
                c.remove()
                logger.info(f"Container {cname} removed")
            except NotFound:
                logger.warning(f"Container {cname} not found")
            except DockerException as e:
                logger.error(f"Failed to remove container {cname}: {e}")

    for vol in [deployment.volume_media, f"{deployment.container_name}_db_data"]:
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
    container_name = deployment.container_name
    db_container_name = f"{container_name}_db"

    try:
        db_container = client.containers.get(db_container_name)
        db_container.restart()
        logger.info(f"Database container {db_container_name} restarted successfully")
    except NotFound:
        create_project_db_container(deployment)
        logger.warning(f"Database container {db_container_name} not found, creating a new one...")

def restart_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False

    # تأكد من قاعدة البيانات أولاً
    restart_docker_db(deployment)

    container_name = deployment.container_name

    try:
        container = client.containers.get(container_name)
        container.restart()
        logger.info(f"Container {container_name} restarted successfully")
    except NotFound:
        create_project_container(deployment)
        logger.warning(f"Container {container_name} not found, creating a new one...")
        

    deployment.status = 2
    deployment.save()
    return True





def stop_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False

    # إيقاف حاوية المشروع
    try:
        container = client.containers.get(deployment.container_name)
        container.stop()
        deployment.status = 1
        deployment.save()
        logger.info(f"Container {deployment.container_name} stopped successfully")
    except NotFound:
        logger.error(f"Container {deployment.container_name} not found")
        return False
    except DockerException as e:
        logger.error(f"Failed to stop container: {e}")
        return False

    # إيقاف قاعدة البيانات (اختياري)
    db_container_name = f"{deployment.container_name}_db"
    try:
        db_container = client.containers.get(db_container_name)
        db_container.stop()
        logger.info(f"Database container {db_container_name} stopped successfully")
    except NotFound:
        logger.warning(f"Database container {db_container_name} not found")
    except DockerException as e:
        logger.error(f"Failed to stop database container: {e}")

    return True

def start_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False

    # تشغيل قاعدة البيانات أولًا
    db_container_name = f"{deployment.container_name}_db"
    try:
        db_container = client.containers.get(db_container_name)
        db_container.start()
        logger.info(f"Database container {db_container_name} started successfully")
    except NotFound:
        create_project_db_container(deployment)
        logger.warning(f"Database container {db_container_name} not found")
    except DockerException as e:
        logger.error(f"Failed to start database container: {e}")

    # تشغيل المشروع
    try:
        container = client.containers.get(deployment.container_name)
        container.start()
        deployment.status = 2
        deployment.save()
        logger.info(f"Container {deployment.container_name} started successfully")
        return True
    except NotFound:
        create_project_container(deployment)
        logger.error(f"Container {deployment.container_name} not found")
        return False
    except DockerException as e:
        logger.error(f"Failed to start container: {e}")
        return False

def get_container_usage(container_name):
    import docker
    client = docker.from_env()
    usage = {}
    db_container_name = f"{container_name}_db"
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

        # ---------------- Storage (Postgres DB) ----------------
        storage_db = 0
        try:
            db_container = client.containers.get(db_container_name)
            exec_result = db_container.exec_run("du -sb /var/lib/postgresql/data")
            storage_db = int(exec_result.output.decode().split()[0])
        except Exception:
            storage_db = 0

        # المجموع النهائي للتخزين
        total_storage = storage_media + storage_db

        usage = {
            "memory_usage": mem_usage,
            "memory_limit": mem_limit,
            "memory_percent": round(mem_percent, 2),
            "cpu_percent": round(cpu_percent, 2),
            "storage_media": storage_media,
            "storage_db": storage_db,
            "storage_usage": total_storage
        }

    except docker.errors.NotFound:
        usage = {"error": f"Container {container_name} not found"}
    except Exception as e:
        usage = {"error": str(e)}

    return usage
