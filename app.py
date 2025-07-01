# app.py

# No more !pip install lines, these are for Colab and handled by requirements.txt

from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import os
import json
import time
from io import BytesIO
import requests
import boxsdk
# No more pyngrok import needed for production deployment
import traceback # ADD THIS LINE

app = Flask(__name__)

# --- Configuration (Load from Environment Variables) ---
# These variables will hold the secrets loaded from environment variables.
# They are accessed directly by the Flask routes and helper functions.
GLOBAL_BOX_JWT_CONFIG = None
GLOBAL_PDF_CO_API_KEY = None

try:
    # Load the JSON string for BOX_JWT_CONFIG from an environment variable
    # We expect the full JSON string to be stored in BOX_JWT_CONFIG_JSON
    jwt_config_json_string = os.environ.get('BOX_JWT_CONFIG_JSON')
    if jwt_config_json_string:
        GLOBAL_BOX_JWT_CONFIG = json.loads(jwt_config_json_string)
        print("BOX_JWT_CONFIG loaded from environment variables.")
    else:
        # This is a critical warning as the app cannot function without it
        print("CRITICAL WARNING: BOX_JWT_CONFIG_JSON environment variable not found or empty.")

    # Load PDF_CO_API_KEY
    GLOBAL_PDF_CO_API_KEY = os.environ.get('PDF_CO_API_KEY')
    if not GLOBAL_PDF_CO_API_KEY:
        # This is a critical warning as the app cannot function without it
        print("CRITICAL WARNING: PDF_CO_API_KEY environment variable not found or empty.")

except Exception as e:
    print(f"CRITICAL ERROR loading secrets from environment variables: {e}")
    # Reset globals to None if there's any loading error to indicate failure
    GLOBAL_BOX_JWT_CONFIG = None
    GLOBAL_PDF_CO_API_KEY = None


# --- HTML Template for the Main Page and Results ---
# Using Tailwind CSS for styling. Load Tailwind from CDN.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Box PDF Merger</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
        .container {
            max-width: 28rem; /* Equivalent to max-w-md */
        }
        input[type="text"]:focus {
            outline: none;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.45); /* Equivalent to focus:ring-2 focus:ring-blue-500 */
        }
        button:not([disabled]) {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); /* shadow-md */
        }
        button:not([disabled]):hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); /* hover:shadow-lg */
        }
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top: 4px solid #fff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-8 rounded-xl shadow-lg w-full container">
        <h1 class="text-3xl font-bold text-gray-800 mb-6 text-center">
            Box PDF Merger
        </h1>

        <form action="/merge-pdfs" method="POST" class="space-y-4" onsubmit="showLoading()">
            <div class="mb-4">
                <label for="folderId" class="block text-gray-700 text-base font-semibold mb-2">
                    Box Folder ID:
                </label>
                <input
                    type="text"
                    id="folderId"
                    name="box_folder_id"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition duration-200"
                    placeholder="e.g., 1234567890"
                    required
                />
            </div>

            <div class="mb-6">
                <label for="mergedFileName" class="block text-gray-700 text-base font-semibold mb-2">
                    Merged PDF File Name:
                </label>
                <input
                    type="text"
                    id="mergedFileName"
                    name="merged_file_name"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition duration-200"
                    placeholder="e.g., My_Combined_Docs.pdf"
                    value="Merged_Box_PDF.pdf"
                    required
                />
            </div>

            <button
                type="submit"
                id="submitButton"
                class="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-semibold hover:bg-blue-700 transition duration-300 ease-in-out"
            >
                Start PDF Merge
            </button>
        </form>

        {% if message %}
            <div class="mt-6 p-4 rounded-lg text-lg {% if 'Error' in message or 'Failed' in message %}bg-red-100 text-red-700{% else %}bg-blue-100 text-blue-700{% endif %}">
                <p class="font-medium">Status:</p>
                <p>{{ message }}</p>
                {% if merged_pdf_url %}
                    <p class="mt-2">Merged PDF: <a href="{{ merged_pdf_url }}" target="_blank" class="text-blue-600 hover:underline">View/Download Here</a></p>
                {% endif %}
            </div>
        {% endif %}

        <div class="mt-8 text-center text-gray-500 text-sm">
            Please ensure your Box JWT configuration (as JSON) and PDF.co API key are set as environment variables.
        </div>
    </div>

    <div id="loadingOverlay" class="loading-overlay" style="display: none;">
        <div class="text-white text-xl flex flex-col items-center">
            <div class="spinner mb-4"></div>
            Processing... This might take a few minutes. Please wait.
        </div>
    </div>

    <script>
        function showLoading() {
            document.getElementById('loadingOverlay').style.display = 'flex';
            document.getElementById('submitButton').disabled = true; // Disable button to prevent multiple submissions
        }
    </script>
</body>
</html>
"""


# --- Box API Helper Functions ---

# ... (your existing app.py code) ...

def initialize_box_client(jwt_config):
    # These prints will appear in your Render logs
    print(f"DEBUG: Entering initialize_box_client. Received jwt_config type: {type(jwt_config)}")
    if jwt_config:
        print(f"DEBUG: jwt_config keys: {list(jwt_config.keys())}")
        if 'boxAppSettings' in jwt_config:
            print(f"DEBUG: boxAppSettings keys: {list(jwt_config['boxAppSettings'].keys())}")
            if 'appAuth' in jwt_config['boxAppSettings']:
                print(f"DEBUG: appAuth keys: {list(jwt_config['boxAppSettings']['appAuth'].keys())}")

    try:
        client_id = jwt_config['boxAppSettings']['clientID']
        client_secret = jwt_config['boxAppSettings']['clientSecret']
        public_key_id = jwt_config['boxAppSettings']['appAuth']['publicKeyID']
        private_key_data = jwt_config['boxAppSettings']['appAuth']['privateKey']
        passphrase_data = jwt_config['boxAppSettings']['appAuth'].get('passphrase')

        print(f"DEBUG: Parsed client_id: {client_id}")
        print(f"DEBUG: Parsed public_key_id: {public_key_id}")
        print(f"DEBUG: Passphrase data (empty string is fine): '{passphrase_data}'")
        print(f"DEBUG: Private key: {private_key_data}")

        auth_params = {
            'client_id': client_id,
            'client_secret': client_secret,
            'jwt_key_id': public_key_id,
            'rsa_private_key_data': private_key_data.encode('utf-8'),
            'rsa_private_key_passphrase': passphrase_data.encode('utf-8') if passphrase_data else None
        }

        print(f"DEBUG: Auth parameters prepared. Calling JWTAuth with enterpriseID: {jwt_config.get('enterpriseID')}, userID: {jwt_config.get('userID')}")
        print(f"DEBUG: Type of JWTAuth (before call): {type(boxsdk.JWTAuth)}")
        print(f"DEBUG: Is JWTAuth callable (before call)? {callable(boxsdk.JWTAuth)}")

        auth = None # Initialize to None for clearer debugging
        if 'enterpriseID' in jwt_config and jwt_config['enterpriseID']:
            auth_params['enterprise_id'] = jwt_config['enterpriseID']
            print(f"DEBUG: JWTAuth repr: {repr(boxsdk.JWTAuth)}")
            auth = boxsdk.JWTAuth(**auth_params)
        elif 'userID' in jwt_config and jwt_config['userID']:
            auth_params['user_id'] = jwt_config['userID']
            print(f"DEBUG: JWTAuth repr: {repr(boxsdk.JWTAuth)}")
            auth = boxsdk.JWTAuth(**auth_params)
        else:
            raise ValueError("Neither 'enterpriseID' nor 'userID' found in BOX_JWT_CONFIG. Cannot determine authentication type.")

        if auth is None: # Added check
            raise RuntimeError("JWTAuth object failed to initialize and is None.")

        print("DEBUG: JWTAuth object created successfully. Attempting to create Client object...")
        return Client(auth)
    except Exception as e:
        print(f"DEBUG: Exception caught inside initialize_box_client: {e}")
        print("DEBUG: Full traceback:")
        full_trace = traceback.format_exc()
        print(f"{full_trace}")
        raise # Re-raise to be caught by the Flask route

# ... (rest of your app.py code) ...

def list_pdf_files_in_box_folder(client, folder_id):
    """
    Lists PDF files in a given Box folder using boxsdk.
    """
    print(f"Listing files in Box folder ID: {folder_id}...")
    try:
        folder = client.folder(folder_id).get()
        pdf_files = []
        items = folder.get_items(limit=100) # Adjust limit as needed for more files
        for item in items:
            if item.type == 'file' and item.name.lower().endswith('.pdf'):
                pdf_files.append({"id": item.id, "name": item.name})
        return pdf_files
    except Exception as e:
        print(f"Error listing files from Box: {e}")
        raise

def download_box_file(client, file_id):
    """
    Downloads a file from Box using boxsdk.
    """
    print(f"Downloading file ID: {file_id} from Box...")
    try:
        box_file = client.file(file_id).get()
        file_content = box_file.content()
        return file_content
    except Exception as e:
        print(f"Error downloading file from Box (ID: {file_id}): {e}")
        raise

def upload_file_to_box(client, folder_id, file_name, file_content):
    """
    Uploads a file to a specified Box folder using boxsdk.
    Returns the uploaded file object from Box SDK.
    """
    print(f"Uploading file '{file_name}' to Box folder ID: {folder_id}...")
    try:
        file_stream = BytesIO(file_content)
        uploaded_file = client.folder(folder_id).upload_stream(file_stream, file_name)
        print(f"Successfully uploaded {file_name} to Box. File ID: {uploaded_file.id}")
        return uploaded_file
    except Exception as e:
        print(f"Error uploading file to Box ('{file_name}'): {e}")
        raise

def create_box_shared_link(client, file_id, access_level='open', can_download=True, can_preview=True):
    """
    Creates or retrieves a shared link for a Box file.
    Returns the shared link URL if successful, otherwise None.
    """
    print(f"Creating shared link for Box file ID: {file_id}...")
    try:
        box_file = client.file(file_id).get()
        updated_file = box_file.update_info(data={
            'shared_link': {
                'access': access_level,
                'can_download': can_download,
                'can_preview': can_preview
            }
        })
        if updated_file and updated_file.shared_link:
            print(f"Shared link created: {updated_file.shared_link['url']}")
            return updated_file.shared_link['url']
        else:
            print("Failed to create shared link (no URL returned).")
            return None
    except Exception as e:
        print(f"Error creating shared link for file ID {file_id}: {e}")
        return None

# --- PDF.co API Helper Functions ---

def upload_file_to_pdf_co(file_name, file_content, api_key):
    """
    Uploads a file to PDF.co temporary storage and returns its URL.
    """
    if not api_key:
        raise ValueError("PDF.co API key not available for upload.")

    presign_url = f"https://api.pdf.co/v1/file/upload/get-presigned-url?name={file_name}"
    headers = { "x-api-key": api_key }
    print(f"Getting presigned URL for '{file_name}' from PDF.co...")
    try:
        response = requests.get(presign_url, headers=headers)
        response.raise_for_status()
        presign_data = response.json()

        if not presign_data['error']:
            upload_url = presign_data['presignedUrl']
            pdf_co_file_url = presign_data['url']

            upload_headers = { "Content-Type": "application/octet-stream" }
            print(f"Uploading '{file_name}' to PDF.co presigned URL...")
            upload_response = requests.put(upload_url, data=file_content, headers=upload_headers)
            upload_response.raise_for_status()
            print(f"Successfully uploaded '{file_name}' to PDF.co temporary storage.")
            return pdf_co_file_url
        else:
            raise RuntimeError(f"PDF.co presigned URL error: {presign_data.get('message', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        print(f"Error during PDF.co file upload for '{file_name}': {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during PDF.co file upload for '{file_name}': {e}")
        raise

def merge_pdfs_pdf_co(file_urls, output_file_name, api_key):
    """
    Initiates the PDF merging process on PDF.co.
    """
    if not api_key:
        raise ValueError("PDF.co API key not available for merging.")

    url = "https://api.pdf.co/v1/pdf/merge"
    headers = { "x-api-key": api_key, "Content-Type": "application/json" }

    payload = {
        "url": ",".join(file_urls),
        "name": output_file_name,
        "async": True,
        "expiration": 60
    }
    print(f"Initiating PDF merge on PDF.co for {len(file_urls)} files...")
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()

        if not result['error']:
            job_id = result['jobId']
            result_url = result['url']
            print(f"PDF.co merge job started. Job ID: {job_id}")
            return job_id, result_url
        else:
            raise RuntimeError(f"PDF.co merge initiation error: {result.get('message', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        print(f"Error calling PDF.co merge API: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during PDF.co merge initiation: {e}")
        raise

def check_pdf_co_job_status(job_id, api_key):
    """
    Checks the status of an asynchronous PDF.co job.
    """
    if not api_key:
        raise ValueError("PDF.co API key not available for job status check.")

    url = f"https://api.pdf.co/v1/job/check?jobid={job_id}"
    headers = { "x-api-key": api_key }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        status_data = response.json()
        return status_data.get('status')
    except requests.exceptions.RequestException as e:
        print(f"Error checking PDF.co job status (Job ID: {job_id}): {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during PDF.co job status check: {e}")
        raise

# --- Core Backend Logic ---

def merge_box_pdfs_backend_logic(box_folder_id, box_client, pdf_co_api_key, merged_file_name):
    """
    Core logic to merge PDFs from Box, process with PDF.co, and upload back to Box.
    Returns a tuple (success: bool, message: str, merged_pdf_url: str or None).
    """
    print("--- Starting PDF Merge Process (Backend Logic) ---")
    merged_box_file_url = None # Initialize to None

    try:
        box_pdf_files = list_pdf_files_in_box_folder(box_client, box_folder_id)
        if not box_pdf_files:
            return False, "No PDF files found in the specified Box folder or an error occurred during listing.", None
        if len(box_pdf_files) < 2:
            return False, "Less than two PDF files found. At least two PDFs are required for merging.", None
        print(f"Found {len(box_pdf_files)} PDF files in Box: {[f['name'] for f in box_pdf_files]}")

        pdf_co_source_urls = []
        for pdf_file in box_pdf_files:
            print(f"Processing '{pdf_file['name']}'...")
            try:
                file_content = download_box_file(box_client, pdf_file['id'])
                pdf_co_url = upload_file_to_pdf_co(pdf_file['name'], file_content, pdf_co_api_key)
                if pdf_co_url:
                    pdf_co_source_urls.append(pdf_co_url)
                else:
                    print(f"Skipping '{pdf_file['name']}' due to PDF.co upload failure (no URL returned).")
            except Exception as e:
                print(f"Skipping '{pdf_file['name']}' due to error during download/upload to PDF.co: {e}")

        if not pdf_co_source_urls:
            return False, "No PDF files were successfully prepared for merging with PDF.co.", None
        print(f"Successfully prepared {len(pdf_co_source_urls)} PDFs for PDF.co merge.")

        job_id, merged_pdf_url_pdf_co = merge_pdfs_pdf_co(pdf_co_source_urls, merged_file_name, pdf_co_api_key)
        if not job_id:
            return False, "Failed to initiate PDF merge on PDF.co (no job ID).", None

        print("Monitoring PDF.co merge job status...")
        status = "working"
        # Add a timeout to prevent infinite loops in production
        timeout_seconds = 300 # 5 minutes timeout
        start_time = time.time()

        while status == "working":
            if time.time() - start_time > timeout_seconds:
                return False, "PDF.co merge job timed out. Please try again.", None
            time.sleep(5) # Wait for 5 seconds before checking again
            status = check_pdf_co_job_status(job_id, pdf_co_api_key)
            print(f"Current PDF.co job status: {status}")
            if status == "success":
                print("PDF.co merge job completed successfully.")
                break
            elif status in ["failed", "aborted"]:
                return False, f"PDF.co merge job {status}.", None

        if status != "success":
            return False, "PDF.co merge job did not complete successfully.", None

        print(f"Downloading merged PDF from PDF.co: {merged_pdf_url_pdf_co}")
        merged_pdf_response = requests.get(merged_pdf_url_pdf_co, allow_redirects=True)
        merged_pdf_response.raise_for_status()
        merged_pdf_content = merged_pdf_response.content
        print("Successfully downloaded merged PDF from PDF.co.")

        # Upload the merged PDF to Box
        uploaded_box_file = upload_file_to_box(box_client, box_folder_id, merged_file_name, merged_pdf_content)

        if uploaded_box_file:
            print(f"Merged PDF '{merged_file_name}' successfully uploaded to Box. Now creating shared link...")
            # Create a shared link for the newly uploaded file
            # Make sure 'open' access is appropriate for your security needs.
            # 'company' or 'collaborators' might be options depending on your Box setup.
            merged_box_file_url = create_box_shared_link(box_client, uploaded_box_file.id, access_level='open', can_download=True)

            if merged_box_file_url:
                return True, f"PDFs merged and uploaded successfully to Box as '{merged_file_name}'.", merged_box_file_url
            else:
                return False, f"PDFs merged and uploaded to Box, but failed to create a shareable link for '{merged_file_name}'. Check your Box folder!", None
        else:
            return False, "Failed to upload merged PDF back to Box.", None

    except Exception as e:
        print(f"An error occurred during the merge process: {e}")
        return False, f"An error occurred during the process: {e}", None

# --- Flask Routes ---

@app.route('/', methods=['GET'])
def index():
    """
    Renders the main page with the input form.
    """
    return render_template_string(HTML_TEMPLATE, message=None, merged_pdf_url=None)

@app.route('/merge-pdfs', methods=['POST'])
def merge_pdfs_endpoint():
    """
    Handles the form submission, triggers the PDF merge logic, and displays results.
    """
    box_folder_id = request.form.get('box_folder_id')
    merged_file_name = request.form.get('merged_file_name', "Merged_Box_PDF.pdf")

    if not box_folder_id:
        return render_template_string(HTML_TEMPLATE, message="Error: Box Folder ID is required.", merged_pdf_url=None)

    if not merged_file_name.lower().endswith('.pdf'):
        return render_template_string(HTML_TEMPLATE, message="Error: Merged file name must end with .pdf", merged_pdf_url=None)

    # Use the globally loaded secrets directly
    if not GLOBAL_BOX_JWT_CONFIG:
        return render_template_string(HTML_TEMPLATE, message="Error: Backend configuration incomplete. Box JWT config not loaded. Check environment variable 'BOX_JWT_CONFIG_JSON'.", merged_pdf_url=None)
    if not GLOBAL_PDF_CO_API_KEY:
        return render_template_string(HTML_TEMPLATE, message="Error: Backend configuration incomplete. PDF.co API key not loaded. Check environment variable 'PDF_CO_API_KEY'.", merged_pdf_url=None)

    box_client = None
    try:
        box_client = initialize_box_client(GLOBAL_BOX_JWT_CONFIG)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, message=f"Error: Box client initialization failed: {e}", merged_pdf_url=None)

    # Call the main merge logic with the global secrets
    success, message, merged_pdf_url = merge_box_pdfs_backend_logic(box_folder_id, box_client, GLOBAL_PDF_CO_API_KEY, merged_file_name)

    return render_template_string(HTML_TEMPLATE, message=message, merged_pdf_url=merged_pdf_url if success else None)

# --- No `if __name__ == '__main__':` block for production ---
# The WSGI server (like Gunicorn) will directly import the `app` object
# from this file and run it.
