import os
import glob
import yaml
import json
from flask import Flask, render_template, abort, request

app = Flask(__name__)
CONFIG_DIR = '/var/www/flask_app/config/'
app_data = []

def get_oidc_user_info():
    """
    Extracts identity data provided by 'OIDCPassIDTokenAs claims'.
    """
    # REMOTE_USER is the standard set by mod_auth_openidc
    username = request.environ.get('REMOTE_USER') or \
               request.environ.get('OIDC_CLAIM_preferred_username') or \
               'unknown_user'

    # Get the groups claim
    raw_groups = request.environ.get('OIDC_CLAIM_groups', '')

    groups = []
    if raw_groups:
        # If the IAM sends a JSON-style list (["a", "b"])
        if raw_groups.startswith('['):
            try:
                import json
                groups = json.loads(raw_groups)
            except:
                groups = [g.strip() for g in raw_groups.split(',')]
        else:
            # If the IAM sends a comma-separated string
            groups = [g.strip() for g in raw_groups.split(',') if g.strip()]
    return {"username": username, "groups": groups}


def load_configs():
    global app_data
    app_data = []
    yaml_files = glob.glob(os.path.join(CONFIG_DIR, "*.yaml"))
    for filepath in yaml_files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)
                data['filename'] = filename
                app_data.append(data)
        except Exception as e:
            app.logger.error(f"Error loading {filename}: {e}")

load_configs()

# --- DEBUG ROUTE ---
@app.route('/debug-auth')
def debug_auth():
    """Returns all OIDC related environment variables for troubleshooting."""
    oidc_vars = {k: v for k, v in request.environ.items() if k.startswith('OIDC_') or k == 'REMOTE_USER'}
    return render_template('form.html',
                           action_name="Auth Debug",
                           description="Listing OIDC Environment Variables",
                           params={},
                           result={"status": "info", "message": "Check the payload below", "received_payload": oidc_vars})

@app.route('/')
def index():
    user = get_oidc_user_info()
    return render_template('index.html', entries=app_data, user=user)

@app.route('/form/<action_name>', methods=['GET', 'POST'])
def action_form(action_name):
    user = get_oidc_user_info()
    yaml_path = os.path.join(CONFIG_DIR, f"{action_name}.yaml")

    if not os.path.exists(yaml_path):
        abort(404)

    with open(yaml_path, 'r') as f:
        metadata = yaml.safe_load(f)

    params = metadata.get('parameters', {})
    result = None

    if request.method == 'POST':
        try:
            from run import run
            # You can now pass user info into your run script for auditing!
            payload = cast_types(request.form, params)
            payload['_triggered_by'] = user['username']
            result = run(payload)
        except Exception as e:
            result = {"status": "error", "message": str(e)}

    return render_template('form.html',
                           action_name=metadata.get('name', action_name),
                           description=metadata.get('description', ''),
                           params=params,
                           result=result,
                           user=user)

def cast_types(form_data, params_metadata):
    casted_data = {}
    for key, meta in params_metadata.items():
        val = form_data.get(key)
        if meta.get('type') == 'boolean':
            casted_data[key] = True if val == 'on' else False
        elif meta.get('type') == 'integer' and val:
            try: casted_data[key] = int(val)
            except: casted_data[key] = val
        elif val == '' and not meta.get('required'):
            casted_data[key] = meta.get('default')
        else:
            casted_data[key] = val
    return casted_data

if __name__ == '__main__':
    app.run()
