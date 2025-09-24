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
import docker
from docker.errors import NotFound, APIError
import logging

logger = logging.getLogger(__name__)

# ---------------- Project containers ----------------
def create_project_container(container):
    """
    ينشئ أو يشغل حاوية Docker لمشروع معين مع إدارة الموارد، التخزين، والبيئة.
    """
    client = docker.from_env()
    pc = container.project_container
    container_name = container.container_name

    # ----------- الحصول على إعدادات Docker ----------- 
    try:
        config = container.to_docker_run_config()
    except Exception as e:
        logger.error(f"Failed to get Docker config for container {container_name}: {e}")
        return False

    # ----------- إضافة الشبكة الافتراضية ----------- 
    network_name = config.get("network") or "deploy_network"
    try:
        client.networks.get(network_name)
    except NotFound:
        try:
            client.networks.create(network_name, driver="bridge")
            logger.info(f"Network '{network_name}' created")
        except APIError as e:
            logger.error(f"Failed to create network '{network_name}': {e}")
            return False
    config["network"] = network_name

    # ----------- تشغيل أو إنشاء الحاوية ----------- 
    try:
        c = client.containers.get(container_name)
        c.start()
        logger.info(f"Project container {container_name} started successfully")
    except NotFound:
        logger.info(f"Project container {container_name} not found, creating a new one...")
        try:
            c = client.containers.run(**config)
            logger.info(f"Project container {container_name} created successfully")
        except APIError as e:
            logger.error(f"Failed to create container {container_name}: {e}")
            return False


    return True


# ---------------- Deployment updater ----------------
def update_deployment(deployment, progress, status):
    deployment.progress = progress
    deployment.status = status
    deployment.save()
    logger.info(f"Deployment {deployment.id} updated: progress={progress}, status={status}")


# ---------------- Runner ----------------
def run_docker(deployment):
    """
    تشغيل جميع حاويات الـ Deployment
    """
    all_ok = True
    for container in deployment.containers.all():
        try:
            ok = create_project_container(container)
            if not ok:
                logger.error(f"Failed to create/start container {container.container_name}")
                all_ok = False
        except Exception as e:
            logger.exception(f"Error deploying container {container.container_name}: {e}")
            all_ok = False

    # تحديث حالة Deployment بعد التشغيل
    if all_ok:
        update_deployment(deployment, progress=4, status=2)  # Completed / Running
        logger.info(f"Deployment {deployment.id} succeeded")
        return True
    else:
        update_deployment(deployment, progress=5, status=3)  # Failed / Undefined
        logger.warning(f"Deployment {deployment.id} failed")
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
    for container in containers:
        cname = container.container_name
        delete_container(client, cname)
    deployment.remove_xfs_volume()
    return True

def rebuild_docker(deployment: Deployment):
    delete_docker(deployment)
    return run_docker(deployment)


def restart_docker(deployment: Deployment):
    client = docker.from_env()
    all_ok = True

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
            create_project_container(dc)
            logger.warning(f"Container {cname} not found, creating a new one...")
        except DockerException as e:
            logger.error(f"Failed to restart container {cname}: {e}")
            all_ok = False

    deployment.status = 2 if all_ok else 3  # Running أو Failed
    deployment.save()
    return all_ok


def hard_restart(deployment: Deployment):
    client = docker.from_env()
    containers = deployment.containers.all()
    for container in containers:
        cname = container.container_name
        delete_container(client, cname)

    restart_docker(deployment)

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

    deployment.status = 1  # Stopped
    deployment.save()
    return all_ok


def start_docker(deployment: Deployment):
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
            container.start()
            logger.info(f"Container {cname} started successfully")
        except NotFound:
            create_project_container(dc)
            logger.warning(f"Container {cname} not found, creating a new one...")
        except DockerException as e:
            logger.error(f"Failed to start container {cname}: {e}")
            all_ok = False

    deployment.status = 2 if all_ok else 3
    deployment.save()
    return all_ok


import subprocess
def get_container_usage(container_name, deployment=None):
    client = docker.from_env()

    def calculate_cpu_percent(stats):
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - stats["precpu_stats"].get("system_cpu_usage", 0)
        cpu_percent = 0.0
        if system_delta > 0.0 and cpu_delta > 0.0:
            percpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            cpu_percent = (cpu_delta / system_delta) * percpu_count * 100.0
        return cpu_percent

    try:
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)

        # -------- RAM --------
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 1)

        # -------- CPU --------
        cpu_percent = calculate_cpu_percent(stats)

        # -------- Storage --------


        return {
            "used_ram": mem_usage,         # Bytes
            "memory_limit": mem_limit,     # Bytes
            "cpu_percent": round(cpu_percent, 1),  # النسبة الفعلية
            
        }

    except docker.errors.NotFound:
        return {"error": f"Container {container_name} not found"}
    except Exception as e:
        return {"error": str(e)}
    
def get_storage_usage(deployment=None):
    used_storage = 0
    if deployment:
        storage_data = deployment.get_volume_storage_data
        mount_dir = storage_data["mount_dir"]

        if os.path.exists(mount_dir):
            try:
                result = subprocess.run(
                    ["du", "-sb", mount_dir],  # <--- هنا mount_dir وليس path
                    capture_output=True,
                    text=True,
                    check=True
                )
                size_bytes = int(result.stdout.split()[0])
                used_storage = size_bytes

            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to get storage usage for {mount_dir}: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error while calculating storage for {mount_dir}: {e}")
        else:
            logger.warning(f"Mount directory does not exist: {mount_dir}")
    return {
        "used_storage": used_storage,  # Bytes
        }