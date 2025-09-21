#deployments\models.py

from django.db import models
from django.contrib.auth.models import User
from projects.models import AvailableProject, EnvVar
import os
import platform
import subprocess
import docker
import re
import logging
logger = logging.getLogger(__name__)

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
        pc = self.project.containers.all()
        if pc.filter(type='backfront').exists():
            return self.containers.get(project_container__type='backfront').domain
        elif pc.filter(type='frontend').exists():
            return self.containers.get(project_container__type='frontend').domain
        else:return 'N/A'
    @property
    def backend_domain(self):
        pc = self.project.containers.all()
        if pc.filter(type='backend').exists():
            return self.containers.get(project_container__type='backend').domain
        else:return 'N/A'

    @property
    def get_volume_storage_data(self):
        """
        تُرجع بيانات التخزين: اسم volume، ملف img (Linux)، ومجلد mount
        """
        volume_name = f"vol_{self.id}"
        system = platform.system()

        if system == "Windows":
            # على Windows استخدم مجلد عادي
            img_path = f"C:\\containers\\data\\{volume_name}"
            mount_dir = f"C:\\containers\\mnt\\{volume_name}"
        else:
            # على Linux استخدم XFS + ملف img
            img_path = f"/var/lib/containers/data/{volume_name}.img"
            mount_dir = f"/mnt/{volume_name}"

        return {
            "volume_name": volume_name,
            "img_path": img_path,
            "mount_dir": mount_dir,
            "system": system
        }

    def create_xfs_volume(self, size_mb=1024):
        """
        ينشئ Docker volume حسب النظام:
        - Linux: XFS + loop + Docker volume
        - Windows: مجلد عادي + Docker volume عادي
        """
        storage_data = self.get_volume_storage_data
        volume_name = storage_data["volume_name"]
        img_path = storage_data["img_path"]
        system = storage_data["system"]

        os.makedirs(os.path.dirname(img_path), exist_ok=True)

        client = docker.from_env()
        existing_volumes = [v.name for v in client.volumes.list()]

        if system == "Linux":
            # 1️⃣ إنشاء ملف img إذا لم يكن موجود
            if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                with open(img_path, "wb") as f:
                    f.truncate(size_mb * 1024 * 1024)

                # 2️⃣ تهيئة XFS
                try:
                    subprocess.run(["mkfs.xfs", "-f", img_path], check=True)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"فشل تهيئة XFS للملف {img_path}: {e}")

            # 3️⃣ إنشاء Docker volume
            if volume_name in existing_volumes:
                volume = client.volumes.get(volume_name)
            else:
                volume = client.volumes.create(
                    name=volume_name,
                    driver="local",
                    driver_opts={
                        "type": "xfs",
                        "device": img_path,
                        "o": "loop"
                    }
                )

        elif system == "Windows":
            # على Windows نستخدم مجلد عادي
            if not os.path.exists(img_path):
                os.makedirs(img_path, exist_ok=True)

            if volume_name in existing_volumes:
                volume = client.volumes.get(volume_name)
            else:
                volume = client.volumes.create(
                    name=volume_name,
                    driver="local"
                )

        else:
            raise RuntimeError(f"نظام التشغيل غير مدعوم: {system}")

        return volume






class DeploymentContainer(models.Model):
    STATUS_CHOICES = [(1,'Pending'),(2,'Running'),(3,'Error')]

    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="containers")
    project_container = models.ForeignKey('projects.ProjectContainer', on_delete=models.CASCADE, null=True)
    container_name = models.CharField(max_length=255)
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
        logger.error(f"env_vars:--> {final_env}")
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
            self.deployment.create_xfs_volume()

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
            config["command"] = pc.command

        # -------------------------------
        # labels + domain + storage info
        # -------------------------------
        labels = self.filter_labels() or {}
        if self.domain:
            labels["custom.domain"] = self.domain
        # نخزن حجم التخزين كـ label فقط
        labels["plan.storage"] = str(storage)
        if labels:
            config["labels"] = labels

        # -------------------------------
        # privileged
        # -------------------------------
        if pc.privileged:
            config["privileged"] = True

        return config


    def resolve_placeholders(self, value):
        """
        استبدال placeholders داخل string أو dict أو list بشكل آمن بدون eval.
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

        pattern = re.compile(r"\{([^}]+)\}")

        def replacer(match):
            expr = match.group(1).strip()
            parts = expr.split(".")

            try:
                # ----------------- container الحالي -----------------
                if parts[0] == "container":
                    # فقط container
                    if len(parts) == 1:
                        return str(self)
                    # container.current.field
                    elif len(parts) == 2:
                        field = parts[1]
                        if field == "container_name":
                            return self.container_name
                        elif field == "domain":
                            return self.domain or ""
                        elif field == "env":
                            return str(self.get_resolved_env_vars())
                        else:
                            return match.group(0)
                    # container.<other>.field
                    elif len(parts) >= 3:
                        target_type_or_name = parts[1]
                        field = parts[2]
                        rest = parts[3:] if len(parts) > 3 else []

                        # البحث عن الكونتينر الهدف حسب النوع أو الاسم
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
                            # 1️⃣ جرب الحصول من DeploymentContainerEnvVar
                            val = target.get_env_vars().get(key)
                            # 2️⃣ إذا لم توجد، استخدم القيمة الافتراضية من ProjectContainer
                            if val is None and target.project_container:
                                val = target.project_container.env_vars.get(key, "")
                            return str(val)
                        elif field == "container_name":
                            return target.container_name
                        elif field == "domain":
                            return target.domain or ""
                        else:
                            return match.group(0)

                # ----------------- fixed_env -----------------
                elif parts[0] in fixed_env:
                    val = fixed_env[parts[0]]
                    for attr in parts[1:]:
                        val = getattr(val, attr, None)
                        if val is None:
                            return match.group(0)
                    return str(val)
                else:
                    return match.group(0)
            except Exception:
                return match.group(0)

        return pattern.sub(replacer, value)



    def get_resolved_env_vars(self):
        """
        إرجاع env_vars بعد حل جميع placeholders بشكل متكرر
        لدعم التعابير المتداخلة بين الكونتينرات.
        """
        # أخذ env_vars من المشروع كقيمة افتراضية
        env_vars = self.project_container.env_vars or {}
        
        # حل placeholders بشكل متكرر
        resolved = env_vars
        max_iter = 5  # لتجنب حلقة لا نهائية
        for _ in range(max_iter):
            new_resolved = {k: self.resolve_placeholders(v) for k, v in resolved.items()}
            if new_resolved == resolved:
                break
            resolved = new_resolved

        return resolved




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