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


# ---------- Deployment Functions ----------
def run_docker(deployment: Deployment, plan: Plan):
    """نشر مشروع باستخدام Docker مع Traefik على Ubuntu"""
    client = docker.from_env()
    container_name = f"{deployment.user.username}_{deployment.project.name}_{deployment.id}".lower()
    db_container_name = f"{container_name}_db"
    image_name = deployment.project.docker_image_name
    volume_media = f"{container_name}_media"
    volume_db = f"{db_container_name}_data"

    ensure_traefik_running(client)

    # التحقق من وجود الصورة
    try:
        client.images.get(image_name)
    except docker.errors.ImageNotFound:
        client.images.pull(image_name)

    # توليد منفذ متاح
    try:
        port = get_free_port()
    except Exception as e:
        update_deployment(deployment, "5", "3", container_name)
        logger.error(f"No free ports available: {e}")
        return False

    # إعداد الموارد
    ram_limit = getattr(plan, "ram", 512)
    cpu_limit = getattr(plan, "cpu", 0.5)
    storage_limit = str(getattr(plan, "storage", '1'))
    mem_limit = f"{ram_limit}m"
    cpu_quota = int(cpu_limit * 100000)

    # إعداد DB vars
    db_name = f"db_{deployment.id}"
    db_user = "postgres"
    db_pass = "postgres"
    db_port = 5432

    # شبكة مشتركة
    network_name = "deploy_network"
    try:
        client.networks.get(network_name)
    except docker.errors.NotFound:
        client.networks.create(network_name, driver="bridge")

    # حذف الحاويات القديمة
    for old in [container_name, db_container_name]:
        try:
            c = client.containers.get(old)
            c.remove(force=True)
            logger.info(f"Removed old container {old}")
        except NotFound:
            pass

    # إنشاء Volumes
    for vol in [volume_media, volume_db]:
        try:
            client.volumes.get(vol)
        except NotFound:
            client.volumes.create(name=vol)
            logger.info(f"Volume {vol} created")

    # تشغيل قاعدة البيانات
    try:
        client.containers.run(
            image="postgres:14",
            name=db_container_name,
            detach=True,
            environment={
                "POSTGRES_DB": db_name,
                "POSTGRES_USER": db_user,
                "POSTGRES_PASSWORD": db_pass,
            },
            volumes={volume_db: {"bind": "/var/lib/postgresql/data", "mode": "rw"}},
            network=network_name,
            restart_policy={"Name": "unless-stopped"}
        )
    except docker.errors.APIError as e:
        logger.error(f"Failed to start DB container {db_container_name}: {e}")
        return False

    # تحديث الحالة
    update_deployment(deployment, "3", "3", container_name)

    # تشغيل حاوية المشروع
    domain = deployment.domain

    # اجمع متغيرات البيئة من DeploymentEnvVar
    env_vars = {env.var_name.key: env.value for env in DeploymentEnvVar.objects.filter(deployment=deployment)}

    # أضف المتغيرات الثابتة المطلوبة مثل USERNAME و DB...
    fixed_env = {
        "USERNAME": deployment.user.username,
        "PLAN": plan.name,
        "PROJECT": deployment.project.name,
        "DOMAIN": domain,        
        "DATABASE_URL": f"postgres://{db_user}:{db_pass}@{db_container_name}:5432/{db_name}",
        "ALLOWED_HOSTS": f"localhost,127.0.0.1,{domain}",
    }

    # دمج الثوابت مع المتغيرات الديناميكية
    final_env = {**fixed_env, **env_vars}
    try:
        container = client.containers.run(
            image=image_name,
            name=container_name,
            labels={
                "traefik.enable": "true",
                f"traefik.http.routers.{container_name}.rule": f"Host(`{domain}`)",
                f"traefik.http.routers.{container_name}.entrypoints": "websecure",
                f"traefik.http.routers.{container_name}.tls.certresolver": "myresolver",
                f"traefik.http.services.{container_name}.loadbalancer.server.port": "8000"
            },
            ports={"8000/tcp": port},
            detach=True,
            mem_limit=mem_limit,
            cpu_quota=cpu_quota,
            # storage_opt={'size': storage_limit},
            volumes={volume_media: {'bind': '/app/media', 'mode': 'rw'}},
            environment=final_env,
            network=network_name,
            restart_policy={"Name": "unless-stopped"}
        )

        deployment.volume_media = volume_media
        update_deployment(deployment, "4", "2", container_name, port)
        deployment.domain = domain
        deployment.save()
        logger.info(f"Deployment succeeded: {container_name} on port {port}")
        return True

    except (DockerException, APIError, ContainerError) as e:
        update_deployment(deployment, "5", "3", container_name)
        logger.error(f"Deployment failed for {container_name}: {e}")
        return False


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

def rebuild_docker(deployment: Deployment, plan: Plan):
    delete_docker(deployment)
    return run_docker(deployment, plan)

def restart_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False
    try:
        container = client.containers.get(deployment.container_name)
        container.restart()
        deployment.status = 2
        deployment.save()
        logger.info(f"Container {deployment.container_name} restarted successfully")
        return True
    except NotFound:
        logger.error(f"Container {deployment.container_name} not found")
        return False
    except DockerException as e:
        logger.error(f"Failed to restart container: {e}")
        return False

def stop_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False
    try:
        container = client.containers.get(deployment.container_name)
        container.stop()
        deployment.status = 1
        deployment.save()
        logger.info(f"Container {deployment.container_name} restarted successfully")
        return True
    except NotFound:
        logger.error(f"Container {deployment.container_name} not found")
        return False
    except DockerException as e:
        logger.error(f"Failed to restart container: {e}")
        return False

def start_docker(deployment: Deployment):
    client = docker.from_env()
    if not deployment.container_name:
        logger.error("No container associated with this deployment")
        return False
    try:
        container = client.containers.get(deployment.container_name)
        container.start()
        deployment.status = 2
        deployment.save()
        logger.info(f"Container {deployment.container_name} restarted successfully")
        return True
    except NotFound:
        logger.error(f"Container {deployment.container_name} not found")
        return False
    except DockerException as e:
        logger.error(f"Failed to restart container: {e}")
        return False

def get_container_usage(container_name):
    import docker
    client = docker.from_env()
    usage = {}
    db_container_name=f"{container_name}_db"
    media_path="/app/media"
    try:
        # الحصول على حاوية المشروع
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)

        # ---------------- RAM ----------------
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 1)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

        # ---------------- CPU ----------------
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            percpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", []))
            cpu_percent = (cpu_delta / system_delta) * percpu_count * 100

        # ---------------- Storage (media) ----------------
        try:
            exec_result = container.exec_run(f"du -sb {media_path}")
            storage_media = int(exec_result.output.decode().split()[0])
        except Exception:
            storage_media = 0

        # ---------------- Storage (Postgres DB) ----------------
        storage_db = 0
        if db_container_name:
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
