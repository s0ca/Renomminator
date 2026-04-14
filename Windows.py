import os
import sys
import webbrowser
import threading
import signal
import time
import zipfile
import shutil
from flask import Flask, request, send_file, render_template, send_from_directory, redirect, url_for
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
from io import BytesIO

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def get_base_path():
    if getattr(sys, 'frozen', False):  # Si l'application est compilée avec PyInstaller
        return sys._MEIPASS  # Dossier temporaire utilisé par PyInstaller
    return os.path.dirname(os.path.abspath(__file__))  # Dossier du script

app = Flask(__name__)

# Définir les dossiers pour stocker les fichiers
BASE_PATH = get_base_path()
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_PATH, 'processed')
UNRENAMED_FOLDER = os.path.join(BASE_PATH, 'unrenamed')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(UNRENAMED_FOLDER, exist_ok=True)

# Fonction pour nettoyer les dossiers avant un nouvel upload
def clear_folders():
    # Supprimer les fichiers dans le dossier UPLOAD_FOLDER
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Supprimer les fichiers dans le dossier PROCESSED_FOLDER
    if os.path.exists(PROCESSED_FOLDER):
        shutil.rmtree(PROCESSED_FOLDER)
        os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Timer pour auto-kill le processus après 1h
def kill_server_after_timeout(timeout):
    time.sleep(timeout)
    print("Killing the server after timeout.")
    os.kill(os.getpid(), signal.SIGTERM)

# Stocker les informations des fichiers renommés et non renommés
renamed_files = []
unrenamed_files = []

# Route principale pour uploader le fichier zip
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global renamed_files, unrenamed_files
    renamed_files = []
    unrenamed_files = []
    
    if request.method == 'POST':
        # Supprimer les fichiers précédents
        clear_folders()
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and file.filename.endswith('.zip'):
            return process_zip(file)  # Process the zip file and return the rendered result
    return render_template('upload.html')

# Route pour afficher une image renommée
@app.route('/processed/<filename>')
def serve_processed_file(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

# Route pour afficher une image non renommée
@app.route('/uploads/<filename>')
def serve_unrenamed_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Fonction pour traiter le fichier zip
def process_zip(zip_file):
    global renamed_files, unrenamed_files
    total_files = 0  # Initialize the counter for .jpg files
    with zipfile.ZipFile(zip_file) as zip_ref:
        zip_ref.extractall(UPLOAD_FOLDER)

    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if filename.endswith('.jpg') and os.path.isfile(file_path):
            total_files += 1  
            new_filename = analyze_and_rename(file_path)
            if new_filename:
                renamed_files.append((filename, new_filename))  # Fichier renommé automatiquement
            else:
                unrenamed_files.append(filename)  # Fichier non renommé ou OCR incorrect

    # Passe les compteurs dans le template de résultat
    return render_template(
        'result.html',
        files=renamed_files + [(f, None) for f in unrenamed_files],
        total_files=total_files,
        renamed_count=len(renamed_files),
        unrenamed_count=len(unrenamed_files),
    )

# Route pour gérer le renommage manuel et générer le ZIP final
@app.route('/handle_manual_rename', methods=['POST'])
def handle_manual_rename():
    manual_renames = request.form.to_dict()

    # Effacer tous les fichiers dans PROCESSED_FOLDER pour éviter les doublons
    for file in os.listdir(PROCESSED_FOLDER):
        file_path = os.path.join(PROCESSED_FOLDER, file)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Mettre à jour les fichiers avec les noms modifiés manuellement
    for original_filename, new_filename in manual_renames.items():
        original_path = os.path.join(UPLOAD_FOLDER, original_filename)
        file_extension = os.path.splitext(original_filename)[1]  # Récupérer l'extension originale (.jpg, .png, etc.)

        # Ajouter automatiquement l'extension si elle n'est pas présente dans le nouveau nom
        if not new_filename.lower().endswith(file_extension.lower()):
            new_filename += file_extension

        final_path = os.path.join(PROCESSED_FOLDER, new_filename)

        # Si un fichier avec ce nom existe déjà, ajouter un suffixe
        base_name, extension = os.path.splitext(final_path)
        suffix_counter = 1
        while os.path.exists(final_path):
            final_path = f"{base_name}_{suffix_counter}{extension}"
            suffix_counter += 1

        # Renommer le fichier
        if os.path.exists(original_path):
            os.rename(original_path, final_path)

    # Générer un fichier ZIP final avec tous les fichiers correctement renommés (manuellement ou automatiquement)
    create_zip([(f, f) for f in os.listdir(PROCESSED_FOLDER)], 'final_renamed_images.zip', PROCESSED_FOLDER)

    # Retourner le fichier ZIP généré
    return send_file(os.path.join(UPLOAD_FOLDER, 'final_renamed_images.zip'), as_attachment=True)

# Fonction pour créer un zip
def create_zip(file_list, zip_name, folder):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as new_zip:
        for original, new_filename in file_list:
            file_path = os.path.join(folder, new_filename)
            if os.path.exists(file_path):
                new_zip.write(file_path, new_filename)

    zip_buffer.seek(0)

    # Sauvegarder le fichier zip temporairement pour l'envoyer
    zip_path = os.path.join(UPLOAD_FOLDER, zip_name)
    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())

# Fonction pour analyser le coin supérieur droit de l'image
def analyze_and_rename(image_path):
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # Recadrer la zone du coin supérieur droit
        box = (width - 450, 0, width - 100, 200)
        cropped_img = img.crop(box)

        # Convertir l'image en niveaux de gris
        grayscale_img = ImageOps.grayscale(cropped_img)

        # Augmenter le contraste
        enhancer = ImageEnhance.Contrast(grayscale_img)
        contrast_img = enhancer.enhance(2.0)

        # Appliquer un seuil de binarisation pour convertir en noir et blanc
        threshold = 128
        binary_img = contrast_img.point(lambda p: p > threshold and 255)

        # Utiliser pytesseract pour extraire le texte à partir de l'image binaire
        number = pytesseract.image_to_string(binary_img, config='--psm 6 -c tessedit_char_whitelist=0123456789').strip()

        if number.isdigit():
            new_filename = f"{number}.jpg"
            new_image_path = os.path.join(PROCESSED_FOLDER, new_filename)
            img.save(new_image_path)
            return new_filename
        else:
            return None
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None
def open_browser():
    webbrowser.open_new('http://127.0.0.1:1337')  # Assurez-vous que le port correspond à celui utilisé par Flask

if __name__ == "__main__":
    timeout_thread = threading.Thread(target=kill_server_after_timeout, args=(3600,))
    timeout_thread.daemon = True  # Permet de s'arrêter proprement avec l'application
    timeout_thread.start()
    # Démarre un thread pour ouvrir le navigateur afin de ne pas bloquer le serveur Flask
    threading.Timer(1.25, open_browser).start()  # Délai court pour laisser le serveur démarrer
    app.run(port=1337, debug=False)
