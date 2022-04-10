import time
from config_head import DB_PATH, API_PASSWORD, SERVERS_PATH, MAX_PARALLEL_UPLOAD, MAX_PARALLEL_DOWNLOAD
import sqlite3
from DbManager import DbManager, loading_control
from Video_nn import *
import requests
import traceback
import threading
import shutil
from io import open as iopen


class ServerHead:
    def __init__(self, db_path, servers_path, password):
        self.pass_header = {'X-PASSWORD': password}
        self.db_manager = DbManager(db_path, servers_path, password)
        self.smpho_dload = threading.BoundedSemaphore(MAX_PARALLEL_DOWNLOAD)
        self.smpho_upload = threading.BoundedSemaphore(MAX_PARALLEL_UPLOAD)

    @loading_control
    def upload_frame(self, proc_id, server_url, frame_path, **params):
        frames_path = frame_path.split('/')[-2]
        filename = frame_path.split('/')[-1]
        extension = filename.split('.')[-1]
        url = f'{server_url}/content/{frames_path}'

        files = [
            ('picture', (
                filename, open(frame_path, 'rb'),
                'image/' + extension))
        ]
        headers = self.pass_header
        try:
            response = requests.request("POST", url, headers=headers, files=files, params=params)
        except requests.ConnectionError:
            return -1
        print(f'Send {frame_path} to {server_url} {datetime.now()}')
        print(response.text)
        if response.status_code == 202:
            return response.json()['output_filename']
        else:
            return -1

    @loading_control
    def download_frame(self, proc_id, server_url, output_path, **params):
        headers = self.pass_header
        try:
            response = requests.get(server_url, params=params, headers=headers)
            # with open(output_path, 'wb') as out_file:
            #     shutil.copyfileobj(response.raw, out_file)
            print(
                f"Download {output_path} from {server_url} {datetime.now()}. Size = {response.headers['content-length']}")
            if response.status_code == 404:
                return -1
            with iopen(output_path, 'wb') as file:
                file.write(response.content)
        except requests.ConnectionError:
            return -1

    def start_work(self, videofile, upd_videofile='untitled.avi', *args_realsr):
        try:
            self.db_manager.check_stuck()
            self.db_manager.prepare_db()
            if len(self.db_manager.get_avlb_servers()) == 0:
                print('All servers are not available')
                return -1
            return_code = improve_video(videofile, upd_videofile, *args_realsr,
                                        func_upscale=self.remote_processing)
            if return_code != 0:
                print('Error. End of work')
                return -1
        except sqlite3.Error as error:
            print("Error while working with sqlite:", error)
            print(traceback.format_exc())
        finally:
            if self.db_manager.sqlite_connection:
                self.db_manager.close_connection()
                print("SQLite connection closed")
        print('Successful complete')

    def download_updates(self, output_frames_path):
        updated = self.db_manager.get_updated()
        for proc_id, frame_url in updated:
            frame_name = frame_url[frame_url.rfind('/') + 1:]
            thread_dload = threading.Thread(target=self.download_frame,
                                            args=(proc_id, frame_url),
                                            kwargs=({'output_path': output_frames_path + frame_name})
                                            )
            thread_dload.start()

    def remote_processing(self, frames_path, upd_frames_path, *args_realsr):
        self.db_manager.add_frames(frames_path)
        self.db_manager.add_upd_frames(upd_frames_path)
        output_frames_path = upd_frames_path.split('/')[-2] + '/'
        while True:
            frame_path = self.db_manager.get_waiting_frame()
            if frame_path is None:
                break
            while True:
                time.sleep(1)
                self.db_manager.watch_servers()
                self.download_updates(upd_frames_path)
                if len(self.db_manager.get_avlb_servers()) == 0:
                    print('All servers are down')
                    return -1
                server_url = self.db_manager.get_vacant_server()
                if server_url is not None:
                    break
            output_name = self.db_manager.get_update_name(frame_path)
            output_path = output_frames_path + output_name
            params = {
                'realsr': ' '.join(args_realsr),
                'output_name': output_name
            }

            proc_id = self.db_manager.add_proc(server_url, frame_path, output_path)
            if self.db_manager.check_exists(server_url, output_path):
                print(f'{output_path} is already on the {server_url}')
                frame_url = server_url + '/content/' + output_path
                dload_path = upd_frames_path + output_name
                thread_dload = threading.Thread(target=self.download_frame,
                                                args=(proc_id, frame_url),
                                                kwargs=({'output_path': dload_path})
                                                )
                thread_dload.start()
            else:
                thread_upload = threading.Thread(target=self.upload_frame,
                                                 args=(proc_id, server_url, frame_path),
                                                 kwargs=params
                                                 )
                thread_upload.start()

        while not self.db_manager.is_all_processed():
            self.db_manager.watch_servers()
            self.download_updates(upd_frames_path)
        return 0


if __name__ == '__main__':
    server_head = ServerHead(DB_PATH, SERVERS_PATH, API_PASSWORD)
    video_dir = 'videos/' + 'barabans/'
    args_realsr = ''
    server_head.start_work(video_dir + 'upbar.mp4', video_dir, *args_realsr.split())
