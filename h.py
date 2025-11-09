import os
import zipfile
import shutil
import glob
import threading
import time
import sys
import urllib.request

# しょきか
_progress_lock = threading.Lock()
_current_message = ""
_progress_current = 0
_progress_total = 0
_last_displayed = -1
_progress_active = False
_download_start_time = 0
_downloaded_bytes = 0
_is_download = False
print("python スクリプト by @kiyu4776")# これケシタラダメ　MITライセンス
# https://github.com/kiyu4776/frida-zip/edit/main

def update_progress(current, total):
    global _progress_current, _progress_total, _downloaded_bytes
    with _progress_lock:
        _progress_current = current
        _progress_total = total
        if _is_download:
            _downloaded_bytes = current


def set_progress_message(msg):
    global _current_message
    with _progress_lock:
        _current_message = msg

#ダウンロード速度
def format_speed(bytes_per_sec):
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:6.1f} B/s"
    elif bytes_per_sec < 1024 ** 2:
        return f"{bytes_per_sec / 1024:6.1f} KB/s"
    elif bytes_per_sec < 1024 ** 3:
        return f"{bytes_per_sec / (1024 ** 2):6.1f} MB/s"
    else:
        return f"{bytes_per_sec / (1024 ** 3):6.1f} GB/s"


def show_progress(stop_event):
    global _progress_current, _progress_total, _last_displayed, _current_message
    global _download_start_time, _downloaded_bytes
    bar_length = 10
    _progress_active = True
    while not stop_event.is_set() or _progress_current < _progress_total:
        with _progress_lock:
            current = _progress_current
            total = _progress_total
            message = _current_message

        if total == 0:
            percent = 0.0
        else:
            percent = min((current / total) * 100, 100.0)

        display_key = int(percent * 10)
        if display_key != _last_displayed:
            filled = int(bar_length * current // max(total, 1))
            bar = "█" * filled + "░" * (bar_length - filled)  # プログレスバー
            if _is_download:
                elapsed = time.time() - _download_start_time
                speed_bps = _downloaded_bytes / elapsed if elapsed > 0 and _downloaded_bytes > 0 else 0
                speed_str = format_speed(speed_bps)
                sys.stdout.write(f"\r{message} : [{bar}] {percent:5.1f}% | {speed_str}")
            else:
                sys.stdout.write(f"\r{message} : [{bar}] {percent:5.1f}%")

            sys.stdout.flush()
            _last_displayed = display_key

        time.sleep(0.05)
    bar = "█" * bar_length
    if _is_download:
        final_elapsed = time.time() - _download_start_time
        final_speed_bps = _downloaded_bytes / final_elapsed if final_elapsed > 0 else 0
        final_speed_str = format_speed(final_speed_bps)
        sys.stdout.write(f"\r{_current_message} : [{bar}] 100.0% | {final_speed_str} 完了\n")
    else:
        sys.stdout.write(f"\r{_current_message} : [{bar}] 100.0% 完了\n")
    sys.stdout.flush()
    _progress_active = False

def start_progress(message, total, is_download=False):
    global _download_start_time, _is_download, _last_displayed
    set_progress_message(message)
    update_progress(0, total)
    _is_download = is_download
    if is_download:
        _download_start_time = time.time()
    _last_displayed = -1

    stop_event = threading.Event()
    thread = threading.Thread(target=show_progress, args=(stop_event,))
    thread.start()
    return stop_event, thread

def end_progress(stop_event, thread):
    update_progress(_progress_total, _progress_total)
    stop_event.set()
    thread.join()

# ================================
def spinner(message, stop_event):
    spinner_chars = ["|", "/", "-", "\\"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{message} : {spinner_chars[i % 4]}")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write(f"\r{message} : 完了\n")
    sys.stdout.flush()

def download_with_progress(url, dest_path, message="ダウンロード中"):
    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get('Content-Length', 0)) or 1

        stop_event, thread = start_progress(message, total_size, is_download=True)

        downloaded = 0
        block_size = 1024 * 64
        with urllib.request.urlopen(url) as response, open(dest_path, 'wb') as f:
            while True:
                data = response.read(block_size)
                if not data:
                    break
                f.write(data)
                downloaded += len(data)
                update_progress(downloaded, total_size)

        end_progress(stop_event, thread)
        return True
    except Exception as e:
        print(f"\n{message} 失敗: {e}")
        try:
            end_progress(stop_event, thread)
        except:
            pass
        return False

# ================================
# ipaファイル検出
def get_ipa_files():
    ipa_files = glob.glob("*.ipa")
    if not ipa_files:
        print("ipaファイルが見つかりません")
        return None
    print("================================")
    for i, ipa in enumerate(ipa_files, 1):
        print(f"{i}: {ipa}")
    return ipa_files


def select_ipa_file(ipa_files):
    print("================================")
    while True:
        try:
            choice = input("処理するipaファイルの番号を入力してください: ")
            index = int(choice) - 1
            if 0 <= index < len(ipa_files):
                return ipa_files[index]
            else:
                print(f"1から{len(ipa_files)}の間で選択してください")
        except ValueError:
            print("数字を入力してください")
def Directory(extracted_path):
    payload_path = os.path.join(extracted_path, "Payload")
    if os.path.exists(payload_path):
        for item in os.listdir(payload_path):
            if item.endswith(".app"):
                app_path = os.path.join(payload_path, item)
                if os.path.isdir(app_path):
                    return app_path
    for root, dirs, _ in os.walk(extracted_path):
        for dir_name in dirs:
            if dir_name.endswith(".app"):
                app_path = os.path.join(root, dir_name)
                if os.path.isdir(app_path):
                    return app_path
    return None


def get_frida_files(extracted_dir):
    frida_files = []
    frida_zip_path = "frida.zip"
    tmp_frida_dir = os.path.join(extracted_dir, "frida_temp")
    download_url = "https://github.com/kiyu4776/frida-zip/raw/refs/heads/main/frida.zip"
    if not os.path.exists(frida_zip_path):
        print("必要なファイルが見つかりません。ダウンロード開始中...")
        if not download_with_progress(download_url, frida_zip_path, "ダウンロード中"):
            return frida_files
    try:
        with zipfile.ZipFile(frida_zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_frida_dir)
        print("モジュールの読み込みが完了")
    except Exception as e:
        print(f"解凍に失敗しました: {e}")
        return frida_files

    if os.path.exists(tmp_frida_dir):
        for root, _, files in os.walk(tmp_frida_dir):
            for file_name in files:
                if file_name == "frida.py":
                    continue
                file_path = os.path.join(root, file_name)
                if os.path.isfile(file_path):
                    frida_files.append((file_path, file_name))
    return frida_files

def extract_ipa_with_progress(ipa_path, extract_to):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total = len(file_list)
            if total == 0:
                print("IPA内にファイルがありません")
                return False
            stop_event, thread = start_progress("解凍中", total, is_download=False)
            extracted = 0
            for file in file_list:
                zip_ref.extract(file, extract_to)
                extracted += 1
                update_progress(extracted, total)
            end_progress(stop_event, thread)
            return True
    except Exception as e:
        print(f"\n解凍に失敗しました: {e}")
        return False

def Build_Ipa(extracted_dir, output_Ipa_Name):
    payload_dir = os.path.join(extracted_dir, "Payload")
    if not os.path.exists(payload_dir):
        print("Payload フォルダが見つかりません")
        return False

    file_list = []
    for root, _, files in os.walk(payload_dir):
        for f in files:
            file_list.append(os.path.join(root, f))

    total = len(file_list)
    if total == 0:
        print("Payload内にファイルがありません")
        return False
    if os.path.exists(output_Ipa_Name):
        while True:
            choice = input(f"'{os.path.basename(output_Ipa_Name)}' は既に存在します。上書きしますか？ (y/n): ").strip().lower()
            if choice == 'y':
                break
            elif choice == 'n':
                # print("処理を中断しました。")
                return False
            else:
                print("y または n を入力してください。")

    stop_event, thread = start_progress("ビルド中", total, is_download=False)
    written = 0
    try:
        if os.path.exists(output_Ipa_Name):
            os.remove(output_Ipa_Name)

        with zipfile.ZipFile(output_Ipa_Name, "w", zipfile.ZIP_DEFLATED) as z:
            for fp in file_list:
                arcname = os.path.relpath(fp, extracted_dir).replace("\\", "/")
                z.write(fp, arcname)
                written += 1
                update_progress(written, total)

        end_progress(stop_event, thread)
        return True
    except Exception as e:
        print(f"\nビルドに失敗しました: {e}")
        end_progress(stop_event, thread)
        return False
# ================================

# 検証A 検証
def iBSS_iBSS_iLLB(Ipa_Name):
    print("検証中...")
    try:
        with zipfile.ZipFile(Ipa_Name, "r") as zip_ref:
            payload_files = [f for f in zip_ref.namelist() if f.startswith("Payload/")]
            if not payload_files:
                print("Payloadフォルダが見つかりません")
                return False
            app_folders = [f for f in payload_files if f.endswith(".app/") and f.count("/") == 2]
            if not app_folders:
                app_folders = [f for f in payload_files if ".app/" in f and "Payload/" in f]
                if not app_folders:
                    print(".appフォルダが見つかりません")
                    return False
            return True
    except Exception as e:
        print(f"IPA検証エラー: {e}")
        return False


def Clean_File(extracted_dir):
    try:
        if os.path.exists(extracted_dir):
            shutil.rmtree(extracted_dir, ignore_errors=True)
    except Exception as e:
        print(f"tmpの削除に失敗しました: {e}")


# ================================
# main
def process_ipa(Ipa_Name):
    current_dir = os.getcwd()
    extracted_dir = os.path.join(current_dir, "tmp")
    Clean_File(extracted_dir)

    try:
        if not extract_ipa_with_progress(Ipa_Name, extracted_dir):
            return None

        app_folder = Directory(extracted_dir)
        if not app_folder:
            print("エラー: .app フォルダが見つかりません")
            return None

        print(f"解凍完了: {os.path.basename(app_folder)}")

        frida_files = get_frida_files(extracted_dir)
        if not frida_files:
            return None

        print("================================")
        stop_event = threading.Event()
        t = threading.Thread(target=spinner, args=("ファイルを追加中", stop_event))
        t.start()

        copied = 0
        for src, dst in frida_files:
            try:
                dest_path = os.path.join(app_folder, dst)
                shutil.copy2(src, dest_path)
                copied += 1
            except Exception as e:
                print(f"\n{dst} のコピーに失敗: {e}")

        stop_event.set()
        t.join()

        base_name = os.path.splitext(Ipa_Name)[0]
        new_Ipa_Name = f"{base_name}_Patch.ipa"
        print("================================")
        if Build_Ipa(extracted_dir, new_Ipa_Name):
            if iBSS_iBSS_iLLB(new_Ipa_Name):
                file_size = os.path.getsize(new_Ipa_Name)
                print(f"ファイルサイズ: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                return new_Ipa_Name
        return None

    except Exception as e:
        print(f"処理中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        Clean_File(extracted_dir)


def main():
    ipa_files = get_ipa_files()
    if not ipa_files:
        return
    selected_ipa = select_ipa_file(ipa_files)
    print("================================")
    print(f"選択されたファイル: {selected_ipa}")
    result_path = process_ipa(selected_ipa)
    if result_path:
        print("================================")
        print(f"完了: {result_path}")
        print("================================")
    else:
        print("処理が中断されました")


if __name__ == "__main__":
    main()
