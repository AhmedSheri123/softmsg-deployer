import os
from pathlib import Path

def run_command(command):
    print(f"Running: {command}")
    os.system(command)

def create_nginx_config(static_folder_name, subdomain, proxy_port, domain, port=80):
    nginx_config = f"""server {{
    listen {port};
    server_name {subdomain}.{domain};

    location /static/ {{
        alias /var/www/hr-original/{static_folder_name}/;
    }}

    # location /media/ {{
    #     alias /var/www/horilla/{subdomain}/media/;
    # }}

    location / {{
        proxy_pass http://77.37.122.10:{proxy_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    error_log /var/log/nginx/{subdomain}_error.log;
    access_log /var/log/nginx/{subdomain}_access.log;
}}"""
    nginx_config_path = f"/etc/nginx/sites-enabled/{subdomain}.conf"
    with open(nginx_config_path, "w") as f:
        f.write(nginx_config)

def restart_services():
    run_command("sudo nginx -s reload")


def remove_file(file_path):
    """Removes a file safely if it exists."""
    try:
        if os.path.exists(file_path):  # Check if the file exists
            os.remove(file_path)  # Delete the file
            print(f"✅ File '{file_path}' removed successfully.")
            return True
        else:
            print(f"⚠️ File '{file_path}' not found.")
            return False
    except Exception as e:
        print(f"❌ Error removing file: {e}")
        return False