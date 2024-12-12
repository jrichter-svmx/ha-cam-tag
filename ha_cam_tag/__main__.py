import logging
import re
import signal
import threading
import time
import json
import os
import requests
import cv2

CONFIG_PATH = "/data/options.json"
API_URL = "http://supervisor/core/api/"
AUTH_TOKEN = os.environ['SUPERVISOR_TOKEN']

# Adjustable variables
FRAME_LIMITER_DELAY = 0.5  # Limit frame processing to every 0.5 seconds (2 FPS)
STREAM_RESTART_DELAY = 5  # Restart stream after this many seconds if interrupted


def send_tag_event(tag_id, device_id, raw_data):
    """
    Send a tag_scanned event to the Home Assistant API.
    """
    endpoint = f"{API_URL}events/tag_scanned"
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    data = {
        "tag_id": tag_id,
        "device_id": device_id,
        "raw_data": raw_data
    }
    response = requests.post(endpoint, headers=headers, json=data)
    if response.status_code != 200:
        logging.error(f"Failed to send event: {response.status_code}, {response.text}")


def detect_qr_code(frame, device_id, tag_id):
    """
    Detect QR codes in the given frame and send their data.
    """
    detector = cv2.QRCodeDetector()
    try:
        if (data := detector.detectAndDecode(frame)[0]):
            send_tag_event(tag_id, device_id, data)
    except Exception as e:
        logging.exception(e)


def main():
    with open(CONFIG_PATH, 'r') as fh:
        config = json.load(fh)

    detector_type = config.get('detector_type', 'qr_code')  # Default to QR code detection
    tag_event_device_id = config['tag_event_device_id']
    camera_stream = config['camera_rtsp_stream']

    exiting = False
    frame = None
    cv = threading.Event()

    def detector_loop():
        """
        Detection processing loop. Extendable for future detectors.
        """
        while not exiting:
            cv.wait()
            try:
                if detector_type == "qr_code":
                    detect_qr_code(frame, tag_event_device_id, tag_event_device_id)
                # Add other detector types here in the future
            except Exception as e:
                logging.exception(e)

    detector_thread = threading.Thread(target=detector_loop)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    detector_thread.start()
    signal.signal(signal.SIGINT, signal.default_int_handler)

    try:
        while True:
            stream = cv2.VideoCapture(camera_stream)
            while stream.isOpened():
                ret, frame = stream.read()
                if ret:
                    cv.set()
                    time.sleep(FRAME_LIMITER_DELAY)  # Use frame limiter delay
            stream.release()
            time.sleep(STREAM_RESTART_DELAY)  # Use stream restart delay
    except KeyboardInterrupt:
        exiting = True
        cv.set()

    detector_thread.join()
    return 0


if __name__ == "__main__":
    main()
