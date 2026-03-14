import cv2
import datetime
import time
import numpy as np

WINDOW_NAME = "Video Recorder"

# 얼굴 / 눈 인식용 Haar Cascade
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)

# PEACE 스티커 PNG 
peace_sticker = cv2.imread("stickers/peace.png", cv2.IMREAD_UNCHANGED)

if peace_sticker is None:
    print("peace.png 파일을 불러올 수 없습니다. stickers/peace.png 경로를 확인하세요.")
    exit()

# 필터 종류
filter_items = [
    ("color", "COLOR"),
    ("gray", "GRAY"),
    ("bulge", "BULGE"),
    ("pinch", "PINCH"),
    ("peace", "PEACE"),
]

selected_filter = "color"
filter_strength = 0.6  # 볼록/오목 필터 강도

# 썸네일 바 높이
thumb_bar_height = 260

# distortion map 캐시
map_cache = {}

# 녹화용 객체
out = None
current_record_filename = None


def get_distortion_maps(width, height, mode, strength):
    key = (width, height, mode, round(strength, 2))
    if key in map_cache:
        return map_cache[key]

    cx = width / 2.0
    cy = height / 2.0

    x = np.arange(width, dtype=np.float32)
    y = np.arange(height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    dx = xx - cx
    dy = yy - cy

    r = np.sqrt(dx * dx + dy * dy)
    max_r = np.sqrt(cx * cx + cy * cy)
    rn = r / max_r

    if mode == "bulge":
        factor = 1.0 - strength * (rn ** 2)
    elif mode == "pinch":
        factor = 1.0 + strength * (rn ** 2)
    else:
        factor = np.ones_like(rn, dtype=np.float32)

    factor = np.where(np.abs(factor) < 1e-6, 1.0, factor)

    src_x = cx + dx / factor
    src_y = cy + dy / factor

    src_x = np.clip(src_x, 0, width - 1).astype(np.float32)
    src_y = np.clip(src_y, 0, height - 1).astype(np.float32)

    map_cache[key] = (src_x, src_y)
    return src_x, src_y


def overlay_png(background, overlay, x, y):
    bh, bw = background.shape[:2]
    oh, ow = overlay.shape[:2]

    if x >= bw or y >= bh or x + ow <= 0 or y + oh <= 0:
        return background

    x1 = max(x, 0)
    y1 = max(y, 0)
    x2 = min(x + ow, bw)
    y2 = min(y + oh, bh)

    overlay_x1 = max(0, -x)
    overlay_y1 = max(0, -y)
    overlay_x2 = overlay_x1 + (x2 - x1)
    overlay_y2 = overlay_y1 + (y2 - y1)

    overlay_crop = overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2]

    if overlay_crop.shape[2] < 4:
        return background

    overlay_rgb = overlay_crop[:, :, :3]
    alpha = overlay_crop[:, :, 3:] / 255.0

    background_region = background[y1:y2, x1:x2]

    blended = background_region * (1 - alpha) + overlay_rgb * alpha
    background[y1:y2, x1:x2] = blended.astype(np.uint8)

    return background


def apply_peace_filter(frame):
    result = frame.copy()
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:
        return result

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face_roi_gray = gray[y:y+h, x:x+w]

    eyes = eye_cascade.detectMultiScale(
        face_roi_gray,
        scaleFactor=1.1,
        minNeighbors=8,
        minSize=(20, 20)
    )

    if len(eyes) >= 2:
        eyes_sorted = sorted(eyes, key=lambda e: e[0], reverse=True)
        ex, ey, ew, eh = eyes_sorted[0]

        eye_center_x = x + ex + ew // 2
        eye_center_y = y + ey + eh // 2

        sticker_size = int(ew * 2.2)
        sticker_x = eye_center_x + int(ew * 0.8)
        sticker_y = eye_center_y - sticker_size // 2
    else:
        sticker_size = max(40, w // 4)
        sticker_x = x + int(w * 0.78)
        sticker_y = y + int(h * 0.28)

    resized_sticker = cv2.resize(peace_sticker, (sticker_size, sticker_size))
    result = overlay_png(result, resized_sticker, sticker_x, sticker_y)

    return result


def apply_filter(frame, mode):
    global filter_strength

    if mode == "color":
        return frame.copy()

    if mode == "gray":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    if mode in ("bulge", "pinch"):
        h, w = frame.shape[:2]
        map_x, map_y = get_distortion_maps(w, h, mode, filter_strength)
        return cv2.remap(frame, map_x, map_y, interpolation=cv2.INTER_LINEAR)

    if mode == "peace":
        return apply_peace_filter(frame)

    return frame.copy()


def build_thumbnail_bar(original_frame, width, selected_mode):
    bar = np.full((thumb_bar_height, width, 3), 245, dtype=np.uint8)

    item_count = len(filter_items)
    item_width = width // item_count

    thumb_y1 = 15
    thumb_y2 = thumb_bar_height - 55
    thumb_h = thumb_y2 - thumb_y1

    for i, (mode, label) in enumerate(filter_items):
        x1 = i * item_width
        x2 = width if i == item_count - 1 else (i + 1) * item_width

        if mode == selected_mode:
            cv2.rectangle(bar, (x1 + 5, 5), (x2 - 5, thumb_bar_height - 5), (215, 230, 255), -1)
            cv2.rectangle(bar, (x1 + 5, 5), (x2 - 5, thumb_bar_height - 5), (50, 120, 255), 2)
        else:
            cv2.rectangle(bar, (x1 + 5, 5), (x2 - 5, thumb_bar_height - 5), (255, 255, 255), -1)
            cv2.rectangle(bar, (x1 + 5, 5), (x2 - 5, thumb_bar_height - 5), (180, 180, 180), 1)

        filtered_thumb = apply_filter(original_frame, mode)

        thumb_w = item_width - 24
        resized_thumb = cv2.resize(filtered_thumb, (thumb_w, thumb_h))

        bar[thumb_y1:thumb_y2, x1 + 12:x1 + 12 + thumb_w] = resized_thumb

        cv2.putText(
            bar,
            label,
            (x1 + 18, thumb_bar_height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (40, 40, 40),
            2
        )

    return bar


def on_mouse(event, x, y, flags, param):
    global selected_filter

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    frame_width, frame_height = param

    if y < frame_height:
        return

    relative_y = y - frame_height
    if relative_y < 0 or relative_y > thumb_bar_height:
        return

    item_width = frame_width // len(filter_items)
    idx = min(x // item_width, len(filter_items) - 1)
    selected_filter = filter_items[idx][0]


def create_new_writer(frame_width, frame_height, fps):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recordings/record_{timestamp}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))
    return writer, filename


# 카메라 열기
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    exit()

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = 20.0

is_recording = False
record_start_time = None

cv2.namedWindow(WINDOW_NAME)
cv2.setMouseCallback(WINDOW_NAME, on_mouse, (frame_width, frame_height))

while True:
    ret, frame = cap.read()
    if not ret:
        print("프레임을 읽을 수 없습니다.")
        break

    filtered_frame = apply_filter(frame, selected_filter)

    cv2.putText(
        filtered_frame,
        f"Filter: {selected_filter.upper()}",
        (20, frame_height - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    if selected_filter in ("bulge", "pinch"):
        cv2.putText(
            filtered_frame,
            f"Strength: {filter_strength:.2f}",
            (20, frame_height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

    # Record 모드
    if is_recording:
        current_elapsed = int(time.time() - record_start_time)

        minutes = current_elapsed // 60
        seconds = current_elapsed % 60
        timer_text = f"REC {minutes:02}:{seconds:02}"

        cv2.circle(filtered_frame, (30, 30), 10, (0, 0, 255), -1)

        cv2.putText(
            filtered_frame,
            timer_text,
            (50, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2
        )

        if out is not None:
            out.write(filtered_frame)

    thumb_bar = build_thumbnail_bar(frame, frame_width, selected_filter)
    display_frame = np.vstack([filtered_frame, thumb_bar])

    cv2.imshow(WINDOW_NAME, display_frame)

    key = cv2.waitKey(1) & 0xFF

    # ESC 키 종료
    if key == 27:
        if out is not None:
            out.release()
            out = None
        break

    # Space 키로 Preview / Record 전환
    elif key == 32:
        if not is_recording:
            # Preview -> Record
            out, current_record_filename = create_new_writer(frame_width, frame_height, fps)
            is_recording = True
            record_start_time = time.time()
            print("Recording started:", current_record_filename)
        else:
            # Record -> Preview
            is_recording = False
            record_start_time = None
            if out is not None:
                out.release()
                print("Recording saved:", current_record_filename)
                out = None
                current_record_filename = None

    # 필터 강도 증가
    elif key == ord('+') or key == ord('='):
        filter_strength = min(1.5, filter_strength + 0.1)
        map_cache.clear()

    # 필터 강도 감소
    elif key == ord('-') or key == ord('_'):
        filter_strength = max(0.1, filter_strength - 0.1)
        map_cache.clear()

cap.release()
cv2.destroyAllWindows()