import os
import sys
import webbrowser
import threading
import signal
import time
import zipfile
import shutil
import re
from flask import Flask, request, send_file, render_template, send_from_directory, redirect, url_for
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
from io import BytesIO


def get_base_path():
    if getattr(sys, 'frozen', False):  # Si l'application est compilée avec PyInstaller
        return sys._MEIPASS  # Dossier temporaire utilisé par PyInstaller
    return os.path.dirname(os.path.abspath(__file__))  # Dossier du script

def configure_tesseract():
    base_path = get_base_path()
    bundle_resources_path = None
    if getattr(sys, 'frozen', False):
        bundle_resources_path = os.path.join(
            os.path.dirname(os.path.dirname(sys.executable)),
            'Resources',
        )

    tesseract_candidates = [
        os.path.join(base_path, 'tesseract', 'tesseract'),
        os.path.join(bundle_resources_path, 'tesseract', 'tesseract') if bundle_resources_path else None,
        shutil.which('tesseract'),
        '/opt/homebrew/bin/tesseract',
        '/usr/local/bin/tesseract',
    ]
    tessdata_candidates = [
        os.path.join(base_path, 'tessdata'),
        os.path.join(bundle_resources_path, 'tessdata') if bundle_resources_path else None,
        '/opt/homebrew/share/tessdata',
        '/usr/local/share/tessdata',
    ]

    for tesseract_path in tesseract_candidates:
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            break

    for tessdata_path in tessdata_candidates:
        if tessdata_path and os.path.exists(os.path.join(tessdata_path, 'eng.traineddata')):
            os.environ.setdefault('TESSDATA_PREFIX', tessdata_path)
            break

app = Flask(__name__)
configure_tesseract()

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

def apply_rotation(image, degrees):
    degrees = degrees % 360
    if degrees == 90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if degrees == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if degrees == 270:
        return image.transpose(Image.Transpose.ROTATE_90)
    return image

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
    rotation_prefix = '__rotation__'
    form_data = request.form.to_dict()
    rotations = {}
    manual_renames = {}

    for field_name, value in form_data.items():
        if field_name.startswith(rotation_prefix):
            original_filename = field_name[len(rotation_prefix):]
            try:
                rotations[original_filename] = int(value) % 360
            except ValueError:
                rotations[original_filename] = 0
        else:
            manual_renames[field_name] = value

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

        # Renommer le fichier en appliquant la rotation choisie dans l'interface.
        if os.path.exists(original_path):
            rotation = rotations.get(original_filename, 0)
            if rotation:
                with Image.open(original_path) as img:
                    rotated_img = apply_rotation(ImageOps.exif_transpose(img), rotation)
                    rotated_img.save(final_path)
                os.remove(original_path)
            else:
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

def clamp_box(box, width, height):
    left, top, right, bottom = box
    return (
        max(0, min(width, int(left))),
        max(0, min(height, int(top))),
        max(0, min(width, int(right))),
        max(0, min(height, int(bottom))),
    )

def get_ocr_boxes(width, height):
    return [
        (width - 450, 0, width - 100, 200),
        (width * 0.58, height * 0.02, width * 0.98, height * 0.22),
        (width * 0.62, height * 0.07, width * 0.96, height * 0.17),
        (width * 0.50, 0, width, height * 0.25),
    ]

def get_ocr_variants(cropped_img):
    grayscale_img = ImageOps.grayscale(cropped_img)
    variants = []

    for contrast in (1.8, 2.5, 3.2):
        contrast_img = ImageEnhance.Contrast(grayscale_img).enhance(contrast)
        variants.append(contrast_img)

        for threshold in (105, 135, 165, 195):
            variants.append(contrast_img.point(lambda p, t=threshold: 0 if p <= t else 255))

    return variants

def extract_number_from_text(text):
    candidates = re.findall(r'\d{4,8}', text)
    for line in text.splitlines():
        compact_line = re.sub(r'\D', '', line)
        if 4 <= len(compact_line) <= 8:
            candidates.append(compact_line)

    if not candidates:
        return None

    return sorted(candidates, key=lambda value: (len(value), value), reverse=True)[0]

def read_case_number(img):
    width, height = img.size

    for raw_box in get_ocr_boxes(width, height):
        box = clamp_box(raw_box, width, height)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue

        cropped_img = img.crop(box)
        for variant in get_ocr_variants(cropped_img):
            for psm in (7, 6, 11):
                text = pytesseract.image_to_string(
                    variant,
                    config=f'--psm {psm} -c tessedit_char_whitelist=0123456789',
                )
                number = extract_number_from_text(text)
                if number:
                    return number

    return None

# Fonction pour analyser le coin supérieur droit de l'image
def analyze_and_rename(image_path):
    try:
        img = ImageOps.exif_transpose(Image.open(image_path))
        number = read_case_number(img)

        if number:
            new_filename = f"{number}.jpg"
            new_image_path = os.path.join(PROCESSED_FOLDER, new_filename)
            img.save(new_image_path)
            return new_filename

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
