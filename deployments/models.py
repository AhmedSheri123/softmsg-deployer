#deployments\models.py

from django.db import models
from django.contrib.auth.models import User
from projects.models import AvailableProject
from django.utils import timezone
import os
import platform
import subprocess
import docker
import re
import logging
import yaml
import shutil

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

SERVICE_PROGRESS = [
    (1, 'Create Project'),
    (2, 'Billing'),
    (3, 'Deploying'),
    (4, 'Completed'),
    (5, 'Failed'),
]

SERVICE_STATUS = [
    (1, 'Stopped'),
    (2, 'Running'),
    (3, 'Undefined'),
]


class Deployment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE)

    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    version = models.CharField(max_length=50, default="1.0")
    progress = models.IntegerField(choices=SERVICE_PROGRESS, null=True)
    status = models.IntegerField(choices=SERVICE_STATUS, null=True)
    is_active = models.BooleanField(default=True)

    used_ram = models.PositiveIntegerField(blank=True, null=True, help_text="RAM used in MB")
    used_storage = models.PositiveIntegerField(blank=True, null=True, help_text="Storage used in GB")
    used_cpu = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, help_text="CPU cores used")
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"{self.user.username} - {self.project.name}"



    @property
    def subscription(self):
        """ترجع الاشتراك المرتبط بهذا الـ Deployment أو None"""
        from plans.models import Subscription
        try:
            return Subscription.objects.get(deployment=self)
        except Subscription.DoesNotExist:
            return None
        
    @property
    def plan(self):
        return self.subscription.plan
    
    def subscription_status(self):
        """ترجع True إذا الاشتراك نشط وجاري"""
        sub = self.subscription
        if sub:
            return sub.has_sub()
        return False

    @property    
    def domain(self):
        dc = self.containers.get(project_container__have_main_domain=True)
        if dc:
            return dc.domain
        return 'N/A'
    
    @property
    def backend_domain(self):
        pc = self.project.containers.all()
        if pc.filter(type='backend').exists():
            return self.containers.get(project_container__type='backend').domain
        else:return 'N/A'




    # ------------------- Volume Storage -------------------
    @property
    def get_volume_storage_data(self):
        """رجوع بيانات التخزين حسب النظام"""
        volume_name = f"vol_{self.id}"
        system = platform.system()

        if system == "Windows":
            img_path = os.path.join("C:\\containers\\data", volume_name)
            mount_dir = os.path.join("C:\\containers\\mnt", volume_name)
        else:
            img_path = f"/var/lib/containers/data/{volume_name}.img"
            mount_dir = f"/mnt/{volume_name}"

        return {
            "volume_name": volume_name,
            "img_path": img_path,
            "mount_dir": mount_dir,
            "system": system
        }

    def create_xfs_volume(self, size_mb=1024):
        """إنشاء volume مركزي لكل Deployment مع تسجيل الأحداث"""

        storage_data = self.get_volume_storage_data
        volume_name = storage_data["volume_name"]
        img_path = storage_data["img_path"]
        mount_dir = storage_data["mount_dir"]
        system = storage_data["system"]

        logger.info(f"Creating XFS volume '{volume_name}' for deployment {self.id} on {system}")

        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        client = docker.from_env()
        existing_volumes = [v.name for v in client.volumes.list()]

        try:
            if system != "Windows":
                logger.info(f"Preparing XFS file at {img_path} ({size_mb} MB)")
                if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                    with open(img_path, "wb") as f:
                        f.truncate(size_mb * 1024 * 1024)
                    logger.info(f"File {img_path} created, formatting XFS")
                    subprocess.run(["mkfs.xfs", "-f", img_path], check=True)
                    logger.info(f"XFS formatting completed for {img_path}")

                if volume_name in existing_volumes:
                    volume = client.volumes.get(volume_name)
                    logger.info(f"Volume '{volume_name}' already exists, using existing")
                else:
                    volume = client.volumes.create(
                        name=volume_name,
                        driver="local",
                        driver_opts={"type": "xfs", "device": img_path, "o": "loop"}
                    )
                    logger.info(f"Volume '{volume_name}' created successfully with XFS")

            else:
                logger.info(f"Windows detected, using directory {img_path}")
                os.makedirs(img_path, exist_ok=True)
                if volume_name in existing_volumes:
                    volume = client.volumes.get(volume_name)
                    logger.info(f"Volume '{volume_name}' already exists, using existing")
                else:
                    volume = client.volumes.create(name=volume_name, driver="local")
                    logger.info(f"Volume '{volume_name}' created successfully on Windows")

            return volume

        except Exception as e:
            logger.exception(f"Failed to create volume '{volume_name}': {e}")
            raise

    def remove_xfs_volume(self):
        """حذف volume مركزي للـ Deployment مع تسجيل الأحداث"""

        storage_data = self.get_volume_storage_data
        volume_name = storage_data["volume_name"]
        img_path = storage_data["img_path"]
        mount_dir = storage_data["mount_dir"]
        system = storage_data["system"]

        logger.info(f"Removing XFS volume '{volume_name}' for deployment {self.id} on {system}")

        client = docker.from_env()

        # حذف Docker volume
        try:
            volume = client.volumes.get(volume_name)
            volume.remove(force=True)
            logger.info(f"Volume '{volume_name}' removed successfully")
        except docker.errors.NotFound:
            logger.warning(f"Volume '{volume_name}' not found, skipping removal")
        except docker.errors.APIError as e:
            logger.error(f"Failed to remove volume '{volume_name}': {e}")

        # حذف ملفات/mount على Linux
        if system != "Windows":
            if os.path.exists(mount_dir):
                try:
                    shutil.rmtree(mount_dir)
                    logger.info(f"Mount directory '{mount_dir}' removed successfully")
                except Exception as e:
                    logger.error(f"Failed to remove mount directory '{mount_dir}': {e}")
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    logger.info(f"Image file '{img_path}' removed successfully")
                except Exception as e:
                    logger.error(f"Failed to remove image file '{img_path}': {e}")


    # ------------------- Compose Rendering -------------------
    def docker_compose(self):
        return yaml.safe_load(self.project.docker_compose_template)
        
    def render_dc_compose(self):
        """Render docker-compose مع volumes فريدة لكل Deployment"""
        logger = logging.getLogger(__name__)
        storage_data = self.get_volume_storage_data
        volume_base_path = storage_data["mount_dir"]
        os.makedirs(volume_base_path, exist_ok=True)
        logger.info(f"Volume base path created: {volume_base_path}")

        compose = self.docker_compose()
        services = compose.get("services", {})
        new_services = {}
        all_volumes = {}

        for name, config in services.items():
            # احصل على container_name من DeploymentContainer
            dc = DeploymentContainer.objects.get(deployment=self, pc_name=name)
            container_name = dc.container_name
            config["container_name"] = container_name

            # إعداد الموارد
            if "deploy" not in config:
                config["deploy"] = {"resources": {"limits": {}}}
            if "limits" not in config["deploy"]["resources"]:
                config["deploy"]["resources"]["limits"] = {}
            config["deploy"]["resources"]["limits"]["cpus"] = str(float(self.plan.cpu))
            config["deploy"]["resources"]["limits"]["memory"] = f"{self.plan.ram}m"

            # الشبكة
            config["networks"] = ["deploy_network"]

            # إعداد volumes فريدة لكل container
            if "volumes" in config:
                new_volumes = []
                for vol_idx, vol in enumerate(config["volumes"]):
                    if isinstance(vol, str) and ":" in vol:
                        _, container_path = vol.split(":", 1)
                    else:
                        container_path = vol if isinstance(vol, str) else f"/vol{vol_idx}"

                    # اجعل اسم المجلد فريد باستخدام self.id واسم container
                    folder_name = f"{container_name}_{container_path.strip('/').replace('/', '_')}"
                    host_path = os.path.join(volume_base_path, folder_name)
                    os.makedirs(host_path, exist_ok=True)

                    if storage_data["system"] == "Windows":
                        host_path = host_path.replace("/", "\\")

                    new_volumes.append(f"{host_path}:{container_path}")
                    all_volumes[folder_name] = None

                config["volumes"] = new_volumes

            new_services[name] = config

        compose["services"] = new_services
        compose["volumes"] = all_volumes
        compose["networks"] = {"deploy_network": {"external": True}}

        logger.info("Docker-compose rendering completed")
        return compose




    def resolve_placeholders(self, value, context=None):
        """
        يدعم:
        {container.<service_name>.<field>}
        {deployment.<field>}
        {dc.<pc_name>.<field>}
        هذه النسخة:
        - recursive على dict/list
        - تمرير context ثابت (compose المعد من render_dc_compose)
        - logging تشخيصي لكل placeholder يتم محاولة حله
        - يدعم استبدال placeholders داخل المفاتيح (keys) والقيم (values)
        """
        if context is None:
            context = {
                "deployment": self,
                "compose": self.render_dc_compose()
            }

        # recursive handling
        if isinstance(value, dict):
            return {
                self.resolve_placeholders(k, context): self.resolve_placeholders(v, context)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.resolve_placeholders(v, context) for v in value]
        if not isinstance(value, str):
            return value

        pattern = re.compile(r"\{([^{}]+)\}")

        def replacer(match):
            expr = match.group(1).strip()
            parts = expr.split(".")
            logger.debug("resolve_placeholder: expr=%s parts=%s", expr, parts)

            try:
                # ---- dc.<pc_name>.<field> ----
                if parts[0] == "dc" and len(parts) >= 3:
                    pc_name = parts[1]
                    subkeys = parts[2:]

                    dc_obj = DeploymentContainer.objects.filter(deployment=self, pc_name=pc_name).first()
                    if not dc_obj:
                        logger.debug("dc not found: deployment=%s pc_name=%s", self.id, pc_name)
                        return match.group(0)
                    node = dc_obj
                    for k in subkeys:
                        node = getattr(node, k, None)
                        if node is None:
                            logger.debug("dc field not found: %s on %s", k, dc_obj)
                            return match.group(0)
                    logger.debug("dc resolved: %s -> %s", expr, node)
                    return str(node)

                # ---- container.<service_name>.<field> ----
                if parts[0] == "container" and len(parts) >= 3:
                    service_name = parts[1]
                    subkeys = parts[2:]
                    services = context.get("compose", {}).get("services", {})
                    svc = services.get(service_name)
                    if svc is None:
                        logger.debug("container service not found in compose: %s", service_name)
                        return match.group(0)
                    node = svc
                    for k in subkeys:
                        if isinstance(node, dict):
                            node = node.get(k)
                        else:
                            node = None
                        if node is None:
                            logger.debug("container field not found: %s on service %s", k, service_name)
                            return match.group(0)
                    logger.debug("container resolved: %s -> %s", expr, node)
                    return str(node)

                # ---- deployment.<field> ----
                if parts[0] == "deployment" and len(parts) >= 2:
                    node = self
                    for k in parts[1:]:
                        node = getattr(node, k, None)
                        if node is None:
                            logger.debug("deployment field not found: %s", k)
                            return match.group(0)
                    logger.debug("deployment resolved: %s -> %s", expr, node)
                    return str(node)

                return match.group(0)
            except Exception as e:
                logger.exception("Error while resolving placeholder %s: %s", expr, e)
                return match.group(0)

        # نعمل عدة مرات لأن placeholders ممكن تكون متداخلة
        prev = value
        for _ in range(5):
            new = pattern.sub(replacer, prev)
            if new == prev:
                break
            prev = new
        return prev



    def get_resolved_compose(self):
        """
        نحصل على compose المعد (render_dc_compose) ثم نمرره كـ context
        ثم نستدعي resolve_placeholders مرة واحدة على whole structure (recursive)
        """
        compose = self.render_dc_compose()
        context = {"deployment": self, "compose": compose}
        resolved = self.resolve_placeholders(compose, context=context)
        return resolved


    
    def render_dc_compose_template(self):
        compose = self.render_dc_compose()
        return yaml.dump(compose, sort_keys=False, default_flow_style=False)

    def render_docker_resolved_compose(self):
        resolved_compose = self.get_resolved_compose()
        return resolved_compose

    def render_docker_resolved_compose_template(self):
        resolved = self.get_resolved_compose()
        return yaml.dump(resolved, sort_keys=False, default_flow_style=False)


class DeploymentContainer(models.Model):
    STATUS_CHOICES = [(1,'Pending'),(2,'Running'),(3,'Error')]

    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="containers")
    container_name = models.CharField(max_length=255)
    pc_name = models.CharField(max_length=255, null=True)
    project_container = models.ForeignKey('projects.ProjectContainer', on_delete=models.CASCADE, null=True)
    domain = models.CharField(max_length=255, blank=True, null=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)

    def __str__(self):
        return f"{self.deployment} | {self.container_name}"

    def get_env_vars(self):
        """
        ترجع قاموس {key: value} لجميع متغيرات البيئة الخاصة بهذا الـ Deployment
        """
        env_vars = {}
        for env in DeploymentContainerEnvVar.objects.filter(container=self):
            if env.var and env.var.key:
                env_vars[env.var.key] = env.get_value
        return env_vars


    def update_default_env_vars(self):
        """
        تقوم بتعبئة جميع DeploymentEnvVar الفارغة بالقيم الافتراضية
        من var.default_value مع دعم تعابير format مثل {self.id} أو {self.domain}.
        """
        env_vars = DeploymentContainerEnvVar.objects.filter(container=self)
        for env in env_vars:
            if (not env.value or env.value.strip() == "") and env.var and env.var.default_value:
                try:
                    # استخدام format لدعم {self} داخل default_value
                    env.value = env.var.default_value.format(container=self)
                except Exception:
                    env.value = env.var.default_value  # fallback لو حصل خطأ
                env.save()

    def get_static_env_vars_list(self):
        return self.project_container.get_env_vars_list()
    
    def get_static_env_var(self, key, default=None):
        return self.project_container.get_env_var(key, default)


    # ---------------- حساب تقسيم الموارد ----------------
    def calculate_resource_limits(self):
        deployment = self.deployment
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
                "cpu": int(cpu_for_container)
            }

        return limits

    def filter_labels(self):
        """
        يُرجع نسخة من labels بعد استبدال المتغيرات من الـ container الحالي.
        """
        pc = self.project_container
        labels = {}

        if not pc or not pc.labels:
            return labels

        # لو labels dict
        if isinstance(pc.labels, dict):
            items = pc.labels.items()
        else:
            # لو جاية كـ list of tuples
            items = pc.labels

        for k, v in items:
            try:
                new_k = str(k).format(container=self)
                new_v = str(v).format(container=self)
            except Exception:
                # fallback لو format فشل
                new_k, new_v = k, v
            labels[new_k] = new_v

        return labels

    def expand_env(self, value, fixed_env):
        """توسيع المتغيرات داخل string أو list أو dict بشكل recursive"""
        if isinstance(value, str):
            try:
                return str(eval(f'f"""{value}"""', {}, fixed_env))
            except Exception:
                return value
        elif isinstance(value, list):
            return [self.expand_env(v, fixed_env) for v in value]
        elif isinstance(value, dict):
            return {k: self.expand_env(v, fixed_env) for k, v in value.items()}
        else:
            return value

    def to_docker_run_config(self):
        """
        تُرجع dict جاهز للاستخدام مع docker-py:
        
        docker.from_env().containers.run(**config)
        """
        if not self.project_container:
            raise ValueError("لا يوجد ProjectContainer مرتبط بهذا الـ DeploymentContainer")

        pc = self.project_container
        container_name = self.container_name
        deployment = self.deployment
        plan = deployment.plan
        
        # ----------- حساب موارد الحاوية -----------
        resource_limits = self.calculate_resource_limits()
        mem_limit = resource_limits.get(container_name, {}).get("mem", f"{getattr(plan, 'ram', 512)}m")
        cpu_cores = resource_limits.get(container_name, {}).get("cpu", getattr(plan, "cpu", 0.5))
        nano_cpus = int(cpu_cores * 1_000_000_000)
        storage = getattr(plan, "storage", 100)  # بالميجابايت (معلومة فقط)

        # -------------------------------
        # الأساسيات
        # -------------------------------
        config = {
            "image": pc.docker_image_name,
            "name": container_name or f"{deployment.id}_{pc.type}",
            "detach": True,
            "environment": {**pc.get_env_vars(), **self.get_env_vars()},
            "restart_policy": {"Name": pc.restart_policy},
            "mem_limit": mem_limit,            # ✅ تحديد الذاكرة
            "nano_cpus":nano_cpus
        }

        # -------------------------------
        # بيئة موسّعة
        # -------------------------------
        env_vars = pc.env_vars or {}
        env_vars = {**env_vars, **self.get_env_vars()}

        # حل جميع المتغيرات، بما فيها الرجوع للكونتينرات الأخرى
        final_env = {k: self.resolve_placeholders(v) for k, v in env_vars.items()}
        
        config["environment"] = final_env
        


        # -------------------------------
        # المنافذ
        # -------------------------------
        if pc.ports:
            port_bindings = {}
            if pc.ports:
                for mapping in pc.ports:
                    for host, container in mapping.items():
                        port_bindings[f"{container}/tcp"] = int(host)

            config["ports"] = port_bindings

        # -------------------------------
        # المجلدات (volumes)
        # -------------------------------
        volumes = {}
        storage_data = self.deployment.get_volume_storage_data
        img_path = storage_data["img_path"]
        mount_dir = storage_data["mount_dir"]

        # 1️⃣ التأكد من وجود ملف XFS
        if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
            self.deployment.create_xfs_volume(storage)
            # logger.error(f"labels:--> {self.resolve_labels(labels)}")

        # 2️⃣ التأكد من وجود mount_dir
        os.makedirs(mount_dir, exist_ok=True)

        # 3️⃣ التحقق من صلاحيات الكتابة
        if not os.access(mount_dir, os.W_OK):
            raise PermissionError(f"لا يمكن الكتابة في {mount_dir}")

        # 4️⃣ إنشاء subfolders وربط كل container_path بنفس img
        for idx, vol in enumerate(pc.volume or []):
            if isinstance(vol, dict) and "container" in vol:
                container_path = vol["container"]
            elif isinstance(vol, str) and ":" in vol:
                _, container_path = vol.split(":", 1)
            else:
                container_path = f"/{vol}" if isinstance(vol, str) else f"/vol{idx}"

            host_path = os.path.join(mount_dir, f"vol{idx}")
            os.makedirs(host_path, exist_ok=True)

            # ربط subfolder بالكونتينر
            volumes[host_path] = {"bind": container_path, "mode": "rw"}

        config["volumes"] = volumes




        # -------------------------------
        # الشبكات
        # -------------------------------
        if pc.networks:
            config["network"] = pc.networks[0]

        # -------------------------------
        # working dir
        # -------------------------------
        if pc.working_dir:
            config["working_dir"] = pc.working_dir

        # -------------------------------
        # entrypoint
        # -------------------------------
        if pc.entrypoint:
            config["entrypoint"] = pc.entrypoint

        # -------------------------------
        # command
        # -------------------------------
        if pc.command:
            command = self.resolve_command(pc.command)
            config["command"] = f"""
            sh -c "{command}"
            """
            logger.error(f"command:--> {command}")

        if pc.healthcheck:
            healthcheck_command = self.resolve_command(pc.healthcheck)
            config["healthcheck"] = healthcheck_command
        # -------------------------------
        # labels + domain + storage info
        # -------------------------------
        labels = self.filter_labels() or {}
        if self.domain:
            labels["custom.domain"] = self.domain
        # نخزن حجم التخزين كـ label فقط
        labels["plan.storage"] = str(storage)
        if labels:
            config["labels"] = self.resolve_labels(labels)
        
        # -------------------------------
        # privileged
        # -------------------------------
        if pc.privileged:
            config["privileged"] = True

        return config



    def resolve_placeholders(self, value):
        """
        استبدال placeholders داخل string أو dict أو list بشكل آمن بدون eval.
        يدعم:
        - container.current.field
        - container.<other>.field
        - container.<other>.env.KEY
        - fixed_env
        - suffix/prefix بعد placeholder
        """
        if isinstance(value, dict):
            return {k: self.resolve_placeholders(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_placeholders(v) for v in value]
        elif not isinstance(value, str):
            return value

        fixed_env = {
            "deployment": self.deployment,
            "plan": getattr(self.deployment, "plan", None),
            "container": self,
            "this_container_domain": self.domain or "",
            "frontend_domain": getattr(self.deployment, "domain", ""),
            "backfront_domain": getattr(self.deployment, "backend_domain", ""),
        }

        pattern = re.compile(r"\{([^{}]+)\}")

        def replacer(match):
            expr = match.group(1).strip()
            parts = expr.split(".")

            try:
                if parts[0] == "container":
                    # container.current.field
                    if len(parts) == 2:
                        field = parts[1]
                        if field == "container_name":
                            return self.container_name
                        elif field == "domain":
                            return self.domain or ""
                        elif field == "env":
                            return str(self.get_resolved_env_vars())
                        else:
                            return match.group(0)

                    # container.<other>.field or env
                    elif len(parts) >= 3:
                        target_type_or_name = parts[1]
                        field = parts[2]
                        rest = parts[3:] if len(parts) > 3 else []

                        # البحث عن الكونتينر الهدف
                        target = self.deployment.containers.filter(
                            project_container__type=target_type_or_name
                        ).first()
                        if not target:
                            target = self.deployment.containers.filter(
                                container_name=target_type_or_name
                            ).first()
                        if not target:
                            return match.group(0)

                        if field == "env" and rest:
                            key = rest[0]
                            val = target.get_resolved_env_vars().get(key)
                            if val is None:
                                val = target.project_container.env_vars.get(key, "")
                            return str(val)
                        elif field == "container_name":
                            return target.container_name
                        elif field == "domain":
                            return target.domain or ""
                        else:
                            return match.group(0)

                # fixed_env
                elif parts[0] in fixed_env:
                    val = fixed_env[parts[0]]
                    for attr in parts[1:]:
                        val = getattr(val, attr, None)
                        if val is None:
                            return match.group(0)
                    return str(val)

                return match.group(0)
            except Exception:
                return match.group(0)

        # حل متكرر لدعم placeholders داخل placeholders
        prev_value = value
        max_iter = 5
        for _ in range(max_iter):
            new_value = pattern.sub(replacer, prev_value)
            if new_value == prev_value:
                break
            prev_value = new_value
        return prev_value


    def get_resolved_env_vars(self):
        """
        إرجاع env_vars بعد حل جميع placeholders بشكل متكرر
        لدعم التعابير المتداخلة بين الكونتينرات.
        """
        env_vars = self.project_container.env_vars or {}
        resolved = env_vars
        max_iter = 5
        for _ in range(max_iter):
            new_resolved = {k: self.resolve_placeholders(v) for k, v in resolved.items()}
            if new_resolved == resolved:
                break
            resolved = new_resolved
        return resolved


    def resolve_labels(self, labels: dict):
        """
        حل جميع placeholders داخل Traefik labels (keys و values) باستخدام نفس منطق env_vars.
        """
        resolved = {}
        for k, v in labels.items():
            new_key = self.resolve_placeholders(k) if isinstance(k, str) else k
            new_value = self.resolve_placeholders(v) if isinstance(v, str) else v
            resolved[new_key] = new_value
        return resolved

    def resolve_command(self, command: str):
        if command:
            command = self.resolve_placeholders(command)
        return command




class DeploymentContainerVolume(models.Model):
    container = models.ForeignKey(DeploymentContainer, on_delete=models.CASCADE, related_name="volumes")
    path = models.CharField(max_length=255, help_text="Path on container/server")
    description = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.container} | {self.path}"


class DeploymentContainerEnvVar(models.Model):
    container = models.ForeignKey(DeploymentContainer, on_delete=models.CASCADE, null=True, related_name="envs")
    var = models.ForeignKey('projects.EnvVar', on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ("container", "var")
        ordering = ["var__sort_index"]
    def __str__(self):
        var_key = self.var.key if self.var else "None"
        container_name = str(self.container) if self.container else "None"
        return f"{container_name} | {var_key} | {self.value}"
    
    @property
    def get_value(self):
        """
        يرجع القيمة محولة حسب نوع EnvVar.data_type
        """
        val = self.value

        # إذا لم توجد قيمة، استخدم default_value من EnvVar
        if not val:
            val = self.var.default_value if self.var else None

        if not val:
            return None

        # تحويل حسب نوع البيانات
        data_type = self.var.data_type if self.var else "string"

        if data_type == "boolean":
            # يقبل True/False أو "1"/"0" أو "true"/"false" كقيم نصية
            if isinstance(val, str):
                return val.lower() in ["true", "1", "yes"]
            return bool(val)
        elif data_type == "int":
            try:
                return int(val)
            except ValueError:
                return 0
        else:  # string
            return str(val)
        



# deployments/models.py
import tarfile





class DeploymentBackup(models.Model):
    BACKUP_TYPE_CHOICES = [
        ("full", "Full (Files + Database)"),
        ("files", "Files Only"),
        ("db", "Database Only"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    deployment = models.ForeignKey("Deployment", on_delete=models.CASCADE, related_name="backups")
    backup_type = models.CharField(max_length=10, choices=BACKUP_TYPE_CHOICES, default="full")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    file_path = models.CharField(max_length=512, blank=True, null=True)
    size_mb = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    restored = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    backup_summary = models.CharField(max_length=255, blank=True, null=True, help_text="Summary of what was backed up")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Backup {self.backup_type} for {self.deployment} at {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    # ---------------------------
    # إنشاء النسخة الاحتياطية
    # ---------------------------
    def create_backup(self):
        logger.info(f"Starting backup for deployment {self.deployment.id}, type={self.backup_type}")
        self.status = "running"
        self.started_at = timezone.now()
        self.backup_summary = ""
        self.save()

        files_backed_up = False
        db_backed_up = False
        backup_file = None

        try:
            os.makedirs("/var/lib/containers/backups", exist_ok=True)

            if self.backup_type in ["full", "files"]:
                try:
                    backup_file_files = self._backup_files()
                    files_backed_up = True
                except Exception as e:
                    logger.warning(f"Files backup failed: {e}")

            if self.backup_type in ["full", "db"]:
                try:
                    backup_file_db = self._backup_database()
                    db_backed_up = True
                except RuntimeError as e:
                    logger.warning(f"Database backup skipped: {e}")
                except Exception as e:
                    logger.error(f"Database backup failed: {e}", exc_info=True)

            # دمج الملفات في حالة full backup
            if self.backup_type == "full":
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
                backup_file = f"/var/lib/containers/backups/deployment_{self.deployment.id}_full_{timestamp}.tar.gz"
                with tarfile.open(backup_file, "w:gz") as tar:
                    if files_backed_up and os.path.exists(backup_file_files):
                        tar.add(backup_file_files, arcname=os.path.basename(backup_file_files))
                    if db_backed_up and os.path.exists(backup_file_db):
                        tar.add(backup_file_db, arcname=os.path.basename(backup_file_db))
            elif self.backup_type == "files":
                backup_file = backup_file_files
            elif self.backup_type == "db":
                backup_file = backup_file_db

            # تحديث summary
            summary_parts = []
            if files_backed_up:
                summary_parts.append("Files")
            if db_backed_up:
                summary_parts.append("Database")
            if summary_parts:
                self.backup_summary = " & ".join(summary_parts) + " backed up successfully"
                if self.backup_type == "full" and (not files_backed_up or not db_backed_up):
                    self.backup_summary += " (partial)"
                if self.status != "failed":
                    self.status = "completed"
            else:
                self.backup_summary = "Backup failed"
                self.status = "failed"

            # إعداد الملف والحجم
            if backup_file and os.path.exists(backup_file):
                self.file_path = backup_file
                self.size_mb = int(os.path.getsize(backup_file) / (1024 * 1024))
                logger.info(f"Backup completed: {backup_file} ({self.size_mb} MB)")
            else:
                if self.status != "failed":
                    self.status = "failed"
                    self.error_message = "Backup file not created"
                    logger.error(f"Backup failed: Backup file not created for deployment {self.deployment.id}")

        except Exception as e:
            self.status = "failed"
            self.error_message = str(e)
            logger.error(f"Backup failed: {e}", exc_info=True)
        finally:
            self.finished_at = timezone.now()
            self.save()

        return self.file_path

    # ---------------------------
    # Restore النسخة الاحتياطية
    # ---------------------------
    def restore_backup(self):
        logger.info(f"Starting restore for backup {self.id}")
        try:
            if self.backup_type == "db":
                self._restore_database()
            else:
                self._restore_full()
            self.restored = True
            logger.info("Restore completed successfully")
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Restore failed: {e}", exc_info=True)
            raise
        finally:
            self.save()

    # ---------------------------
    # نسخ الملفات فقط
    # ---------------------------
    def _backup_files(self):
        storage_data = self.deployment.get_volume_storage_data
        mount_dir = storage_data["mount_dir"]
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        backup_file = f"/var/lib/containers/backups/deployment_{self.deployment.id}_files_{timestamp}.tar.gz"

        logger.info(f"Backing up files to {backup_file}")
        with tarfile.open(backup_file, "w:gz") as tar:
            if os.path.exists(mount_dir):
                tar.add(mount_dir, arcname=f"deployment_{self.deployment.id}_data")
        return backup_file

    # ---------------------------
    # نسخ قاعدة البيانات فقط
    # ---------------------------
    def _backup_database(self):
        env = self._get_db_env()
        db_name = env["db_name"]
        db_user = env["db_user"]
        db_password = env["db_password"]
        db_host = env["db_host"]
        db_port = env["db_port"]
        container_name = env["container_name"]

        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        backup_file = f"/var/lib/containers/backups/{db_name}_{timestamp}.sql.gz"
        logger.info(f"Backing up database to {backup_file}")

        os.makedirs(os.path.dirname(backup_file), exist_ok=True)

        if db_host in [c.container_name for c in self.deployment.containers.all()]:
            cmd = f"docker exec {container_name} pg_dump -U {db_user} {db_name} | gzip > {backup_file}"
            logger.info(f"Running command: {cmd}")
            subprocess.run(cmd, shell=True, check=True)
        else:
            env_vars = os.environ.copy()
            env_vars["PGPASSWORD"] = db_password
            temp_file = backup_file.replace(".gz", "")
            with open(temp_file, "wb") as f:
                cmd = ["pg_dump", "-h", db_host, "-p", str(db_port), "-U", db_user, "-d", db_name]
                logger.info(f"Running command: {' '.join(cmd)}")
                subprocess.run(cmd, stdout=f, check=True, env=env_vars)
            subprocess.run(["gzip", "-f", temp_file], check=True)

        return backup_file

    # ---------------------------
    # Restore Full
    # ---------------------------
    def _restore_full(self):
        storage_data = self.deployment.get_volume_storage_data
        mount_dir = storage_data["mount_dir"]
        os.makedirs(mount_dir, exist_ok=True)

        logger.info(f"Restoring full backup from {self.file_path} to {mount_dir}")
        with tarfile.open(self.file_path, "r:gz") as tar:
            tar.extractall(path=mount_dir)
        logger.info("Full restore completed")

    # ---------------------------
    # Restore Database
    # ---------------------------
    def _restore_database(self):
        env = self._get_db_env()
        db_name = env["db_name"]
        db_user = env["db_user"]
        db_password = env["db_password"]
        db_host = env["db_host"]
        db_port = env["db_port"]
        container_name = env["container_name"]

        logger.info(f"Restoring database {db_name} from {self.file_path}")

        if db_host in [c.container_name for c in self.deployment.containers.all()]:
            cmd = f"gunzip -c {self.file_path} | docker exec -i {container_name} psql -U {db_user} -d {db_name}"
            logger.info(f"Running command: {cmd}")
            subprocess.run(cmd, shell=True, check=True)
        else:
            env_vars = os.environ.copy()
            env_vars["PGPASSWORD"] = db_password
            with open(self.file_path, "rb") as f:
                subprocess.run(
                    ["psql", "-h", db_host, "-p", str(db_port), "-U", db_user, "-d", db_name],
                    input=f.read(),
                    check=True,
                    env=env_vars
                )
        logger.info("Database restore completed")

    # ---------------------------
    # جلب بيانات DB من المشروع والحاوية
    # ---------------------------
    def _get_db_env(self):
        db_config = getattr(self.deployment.project, "db_config", None)
        if not db_config or not db_config.is_valid():
            raise RuntimeError("No valid DB config found for this project. Backup cannot proceed.")

        db_container = self.deployment.containers.filter(
            project_container__type="db"
        ).first()
        if not db_container:
            raise RuntimeError("No database container found for this deployment")

        env = db_container.get_resolved_env_vars()
        return {
            "db_name": env.get(db_config.db_name),
            "db_user": env.get(db_config.db_user),
            "db_password": env.get(db_config.db_password),
            "db_host": db_container.container_name,
            "db_port": env.get(db_config.db_port, "5432"),
            "container_name": db_container.container_name
        }