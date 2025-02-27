from PIL import Image
from zipfile import ZipFile
import glob
import os
import shutil
import multiprocessing
import sys
from ctypes import windll, wintypes, byref

THUMBNAIL_NAME = '_thumbnail.png'

def modify_ctime(path, ctime):
    #https://stackoverflow.com/questions/4996405/how-do-i-change-the-file-creation-date-of-a-windows-file
    # Arbitrary example of a file and a date
    filepath = path
    epoch = ctime

    # Convert Unix timestamp to Windows FileTime using some magic numbers
    # See documentation: https://support.microsoft.com/en-us/help/167296
    timestamp = int((epoch * 10000000) + 116444736000000000)
    ctime = wintypes.FILETIME(timestamp & 0xFFFFFFFF, timestamp >> 32)

    # Call Win32 API to modify the file creation date
    handle = windll.kernel32.CreateFileW(filepath, 256, 0, None, 3, 128, None)
    windll.kernel32.SetFileTime(handle, byref(ctime), None, None)
    windll.kernel32.CloseHandle(handle)

def get_thread_number():
    number_of_thread = multiprocessing.cpu_count() - 1
    if number_of_thread == 0:
        return 1
    else:
        return number_of_thread

def split_to_chunks(image_paths, n):
    return [image_paths[i::n] for i in range(n)]

def convert_images(image_paths, options, shared_queue):
    for image_path in image_paths:
        image = Image.open(image_path)
        image.save(os.path.splitext(image_path)[0] + '.webp', method=6, lossless=options['lossless'], quality=options['quality'])

    for image_path in image_paths:
        os.remove(image_path)

    shared_queue.put(True)
    return

def generate_thumbnail(folder_path):
    MAX_SIZE = 640
    image_paths = get_file_paths_by_extensions(folder_path, ['jpg', 'png', 'webp', 'gif'])

    # Generate thumbnail only if images exist
    if not image_paths:
        return

    # Select first image
    image_path = image_paths[0]

    image = Image.open(image_path)
    width, height = image.size
    resize_ratio = min(MAX_SIZE/width, MAX_SIZE/height)
    resized_resolution = (int(width*resize_ratio), int(height*resize_ratio))
    thumbnail = image.resize(resized_resolution)
    thumbnail.save(os.path.join(folder_path, THUMBNAIL_NAME))

def get_file_paths_by_extensions(folder_path, extensions):
    file_paths = []
    for extension in extensions:
        paths = glob.glob(glob.escape(folder_path) + '\\*.' + extension)
        for path in paths:
            if not os.path.basename(path) == THUMBNAIL_NAME:
                file_paths.append(path)

    return file_paths

def recover_zip(folder_path, backup_path, zip_file_path):
    os.rename(backup_path, zip_file_path)
    shutil.rmtree(folder_path)
    raise NameError('Error during processing images')

def slimify(zip_file_path, options):
    print('Processing', zip_file_path)

    # Save file time info
    file_time = (os.stat(zip_file_path).st_atime, os.stat(zip_file_path).st_mtime)
    ctime = os.stat(zip_file_path).st_ctime

    # Unzip and make backup
    folder_path, extension = os.path.splitext(zip_file_path)
    shutil.unpack_archive(zip_file_path, folder_path, 'zip')
    if not os.path.exists(folder_path):
        raise NameError('File name cannot be folder name')
    backup_path = zip_file_path + '.back'
    os.rename(zip_file_path, backup_path)

    # Find jpg or png
    image_paths = get_file_paths_by_extensions(folder_path, ['jpg', 'png', 'jpeg'])
    image_path_chunks = split_to_chunks(image_paths, get_thread_number())

    # Generate thumbnail if needed
    if options['thumbnail']:
        generate_thumbnail(folder_path)

    # Convert images
    processes = []
    shared_queue = multiprocessing.Queue()
    for i in range(get_thread_number()):
        p = multiprocessing.Process(target=convert_images, args=(image_path_chunks[i], options, shared_queue))
        processes.append(p)
        p.start()
    for process in processes:
        process.join()

    # Check if error occured in multiprocessing
    if shared_queue.qsize() != get_thread_number():
        recover_zip(folder_path, backup_path, zip_file_path)
        return
    
    # Rezip the folder
    converted_zip_path = shutil.make_archive(folder_path, 'zip', folder_path)

    # Recover file time info
    os.utime(converted_zip_path, file_time)
    modify_ctime(converted_zip_path, ctime)


    # Remove old zip file and folder
    shutil.rmtree(folder_path)
    os.remove(backup_path)

def get_lossless_option():
    print('Select lossy or lossless (Default = lossy)')
    print('1. Lossy')
    print('2. Lossless')

    answer = input()

    if answer == '2':
        return True
    else:
        return False

def get_quality_option():
    DEFAULT = 80
    print('Select quality parameter 1-100 (Default = 80)')
    answer = input()

    if answer.isdecimal() == False:
        return DEFAULT
    
    answer_number = int(answer)

    if 0 < answer_number <= 100:
        return answer_number
    else:
        return DEFAULT

def get_thumbnail_option():
    print('Generate thumbnail? (for CBXShell) (Default = No)')
    print('1. Yes')
    print('2. No')

    answer = input()

    if answer == '1':
        return True
    else:
        return False

if __name__ == '__main__':
    # Windows exe support
    multiprocessing.freeze_support()

    options = {
        'lossless': get_lossless_option(),
        'quality': get_quality_option(),
        'thumbnail': get_thumbnail_option()
    }

    # In lossless mode, quality means speed
    if options['lossless']:
        options['quality'] = 100

    # Find zip files
    zip_file_paths = glob.glob('**/*.zip', recursive=True)
    print(zip_file_paths)

    # Process zip files
    for index, zip_file_path in enumerate(zip_file_paths):
        print('Processing', index, '/', len(zip_file_paths))
        try:
            slimify(zip_file_path, options)
        except Exception as err:
            print(f'Error during {zip_file_path}', err)
            with open('errorlog.txt', 'a+') as f:
                f.write(f'Error during {zip_file_path} {err}\n')

    print('Process finished')
    print('Press Enter to exit')
    input()