import os
import re
import time
from io import BytesIO
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).with_name(".matplotlib")))

import cv2
import matplotlib.pyplot as plt
import mss
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageGrab

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightError = Exception
    PlaywrightTimeoutError = Exception
    sync_playwright = None

try:
    import pytesseract
    from pytesseract import Output, TesseractNotFoundError
except ImportError:
    pytesseract = None
    Output = None

    class TesseractNotFoundError(Exception):
        pass


AMOUNT_PATTERN = re.compile(
    r"(?<![\w])(?:[$€£Ar]|USD|EUR|MGA)?\s*"
    r"(?:\d{1,3}(?:[,\s]\d{3})+|\d+)(?:[.,]\d+)?"
    r"(?!\s*[xX])",
    re.IGNORECASE,
)

DEFAULT_GAME_URL = "https://bet261.mg/instant-games/llc/Aviator?categoryId=18"


def init_state() -> None:
    defaults = {
        "scan_running": False,
        "history": [],
        "last_result": None,
        "last_image": None,
        "last_error": "",
        "url_scan_running": False,
        "url_playwright": None,
        "url_browser": None,
        "url_page": None,
        "url_current": "",
        "url_session_blue": 0,
        "url_session_other": 0,
        "url_session_total": 0,
        "url_last_round_signature": "",
        "url_last_round_time": 0.0,
        "url_round_events": [],
        "last_analysis_source": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_scan() -> None:
    st.session_state.scan_running = True
    st.session_state.url_scan_running = False


def stop_scan() -> None:
    st.session_state.scan_running = False


def start_url_scan() -> None:
    reset_url_session()
    st.session_state.url_scan_running = True
    st.session_state.scan_running = False


def stop_url_scan() -> None:
    st.session_state.url_scan_running = False
    close_url_browser()


def clear_history() -> None:
    st.session_state.history = []


def reset_url_session() -> None:
    st.session_state.url_session_blue = 0
    st.session_state.url_session_other = 0
    st.session_state.url_session_total = 0
    st.session_state.url_last_round_signature = ""
    st.session_state.url_last_round_time = 0.0
    st.session_state.url_round_events = []


def close_url_browser() -> None:
    for key in ("url_page", "url_browser"):
        resource = st.session_state.get(key)
        if resource is not None:
            try:
                resource.close()
            except Exception:
                pass
            st.session_state[key] = None

    playwright_runtime = st.session_state.get("url_playwright")
    if playwright_runtime is not None:
        try:
            playwright_runtime.stop()
        except Exception:
            pass
        st.session_state.url_playwright = None

    st.session_state.url_current = ""


def read_clipboard_image() -> tuple[Image.Image | None, str]:
    try:
        clipboard_content = ImageGrab.grabclipboard()
    except Exception as exc:
        return None, f"Impossible de lire le presse-papiers : {exc}"

    if isinstance(clipboard_content, Image.Image):
        return clipboard_content.convert("RGB"), ""

    if isinstance(clipboard_content, list) and clipboard_content:
        first_file = clipboard_content[0]
        try:
            return Image.open(first_file).convert("RGB"), ""
        except Exception as exc:
            return None, f"Le fichier du presse-papiers n'est pas une image lisible : {exc}"

    return None, "Aucune image trouvee dans le presse-papiers. Faites PrtSc ou Win+Shift+S, puis reessayez."


def capture_screen_region(x: int, y: int, width: int, height: int) -> Image.Image:
    monitor = {"left": x, "top": y, "width": width, "height": height}
    with mss.MSS() as sct:
        screenshot = sct.grab(monitor)

    frame = np.array(screenshot)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    return Image.fromarray(rgb_frame)


def ensure_url_page(
    url: str,
    show_browser: bool,
    viewport_width: int,
    viewport_height: int,
    initial_wait_seconds: int,
):
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright n'est pas installe. Lancez : pip install -r requirements.txt puis python -m playwright install chromium"
        )

    page = st.session_state.get("url_page")
    browser = st.session_state.get("url_browser")
    if page is not None and browser is not None and st.session_state.url_current == url:
        return page

    close_url_browser()

    playwright_runtime = sync_playwright().start()
    browser = playwright_runtime.chromium.launch(headless=not show_browser)
    page = browser.new_page(viewport={"width": viewport_width, "height": viewport_height})
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(initial_wait_seconds * 1000)

    st.session_state.url_playwright = playwright_runtime
    st.session_state.url_browser = browser
    st.session_state.url_page = page
    st.session_state.url_current = url
    return page


def capture_url_page(
    url: str,
    show_browser: bool,
    viewport_width: int,
    viewport_height: int,
    initial_wait_seconds: int,
) -> Image.Image:
    page = ensure_url_page(url, show_browser, viewport_width, viewport_height, initial_wait_seconds)
    screenshot = page.screenshot(full_page=False)
    return Image.open(BytesIO(screenshot)).convert("RGB")


def crop_by_percent(
    image: Image.Image,
    left_pct: int,
    top_pct: int,
    width_pct: int,
    height_pct: int,
) -> Image.Image:
    img_width, img_height = image.size
    left = int(img_width * left_pct / 100)
    top = int(img_height * top_pct / 100)
    right = min(img_width, left + int(img_width * width_pct / 100))
    bottom = min(img_height, top + int(img_height * height_pct / 100))
    return image.crop((left, top, right, bottom))


def image_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((32, 16))
    pixels = np.array(gray)
    threshold = pixels.mean()
    bits = pixels > threshold
    packed = np.packbits(bits.astype(np.uint8))
    return packed.tobytes().hex()


def selected_latest_candidate(
    result: dict,
    latest_position: str,
) -> tuple[str, tuple[int, int, int, int]] | None:
    candidates = [("blue", box) for box in result["blue_boxes"]]
    candidates += [("other", box) for box in result["other_boxes"]]

    if not candidates:
        return None

    if latest_position == "Gauche":
        return min(candidates, key=lambda item: (item[1][0], item[1][1]))
    if latest_position == "Droite":
        return max(candidates, key=lambda item: (item[1][2], -item[1][1]))
    if latest_position == "Haut":
        return min(candidates, key=lambda item: (item[1][1], item[1][0]))
    return max(candidates, key=lambda item: (item[1][3], item[1][0]))


def update_url_session_counter(
    image: Image.Image,
    result: dict,
    latest_position: str,
    min_seconds_between_rounds: int,
) -> tuple[dict, str]:
    candidate = selected_latest_candidate(result, latest_position)
    if candidate is None:
        return session_result_from_visible(result), "Aucun multiplicateur detecte dans la zone historique URL."

    category, box = candidate
    left = max(0, box[0] - 4)
    top = max(0, box[1] - 4)
    right = min(image.width, box[2] + 4)
    bottom = min(image.height, box[3] + 4)
    round_crop = image.crop((left, top, right, bottom))
    round_signature = f"{category}:{image_hash(round_crop)}"
    now = time.time()

    if not st.session_state.url_last_round_signature:
        st.session_state.url_last_round_signature = round_signature
        st.session_state.url_last_round_time = now
        return session_result_from_visible(result), (
            "Point de depart enregistre. Le compteur commencera au prochain nouveau tour detecte."
        )

    if round_signature != st.session_state.url_last_round_signature:
        elapsed = now - float(st.session_state.url_last_round_time or 0)
        if elapsed >= min_seconds_between_rounds:
            if category == "blue":
                st.session_state.url_session_blue += 1
                category_label = "Bleu"
            else:
                st.session_state.url_session_other += 1
                category_label = "Autres couleurs"

            st.session_state.url_session_total += 1
            st.session_state.url_round_events.append(
                {
                    "datetime": result["datetime"],
                    "categorie": category_label,
                    "position": latest_position,
                }
            )
            st.session_state.url_last_round_time = now

        st.session_state.url_last_round_signature = round_signature

    return session_result_from_visible(result), ""


def session_result_from_visible(result: dict) -> dict:
    session_result = dict(result)
    total, blue_pct, other_pct = compute_percentages(
        st.session_state.url_session_blue,
        st.session_state.url_session_other,
    )
    session_result["blue"] = st.session_state.url_session_blue
    session_result["other"] = st.session_state.url_session_other
    session_result["total"] = total
    session_result["blue_pct"] = blue_pct
    session_result["other_pct"] = other_pct
    return session_result


def find_grouped_boxes(mask: np.ndarray, min_area: int, merge_distance: int) -> list[tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 2 or h < 2:
            continue
        boxes.append((x, y, x + w, y + h))

    return merge_boxes(boxes, merge_distance)


def merge_boxes(boxes: list[tuple[int, int, int, int]], distance: int) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []

    for box in boxes:
        current = box
        did_merge = True

        while did_merge:
            did_merge = False
            remaining = []

            for other in merged:
                if boxes_are_close(current, other, distance):
                    current = (
                        min(current[0], other[0]),
                        min(current[1], other[1]),
                        max(current[2], other[2]),
                        max(current[3], other[3]),
                    )
                    did_merge = True
                else:
                    remaining.append(other)

            merged = remaining

        merged.append(current)

    return sorted(merged, key=lambda b: (b[1], b[0]))


def boxes_are_close(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    distance: int,
) -> bool:
    horizontal_gap = max(0, max(first[0], second[0]) - min(first[2], second[2]))
    vertical_gap = max(0, max(first[1], second[1]) - min(first[3], second[3]))
    heights_overlap = min(first[3], second[3]) >= max(first[1], second[1]) - distance
    widths_overlap = min(first[2], second[2]) >= max(first[0], second[0]) - distance
    return (horizontal_gap <= distance and heights_overlap) or (
        vertical_gap <= distance and widths_overlap
    )


def detect_colored_multipliers(
    image: Image.Image,
    hsv_low: tuple[int, int, int],
    hsv_high: tuple[int, int, int],
    min_saturation: int,
    min_value: int,
    min_area: int,
    merge_distance: int,
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    rgb = np.array(image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    blue_mask = cv2.inRange(hsv, np.array(hsv_low), np.array(hsv_high))
    colored_mask = cv2.inRange(
        hsv,
        np.array((0, min_saturation, min_value)),
        np.array((179, 255, 255)),
    )
    other_mask = cv2.bitwise_and(colored_mask, cv2.bitwise_not(blue_mask))

    kernel = np.ones((2, 2), np.uint8)
    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
    other_mask = cv2.morphologyEx(other_mask, cv2.MORPH_CLOSE, kernel)

    blue_boxes = find_grouped_boxes(blue_mask, min_area, merge_distance)
    other_boxes = find_grouped_boxes(other_mask, min_area, merge_distance)
    return blue_boxes, other_boxes


def parse_amount(raw_value: str) -> float | None:
    cleaned = re.sub(r"[^\d,.\s-]", "", raw_value).strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace(" ", "")
    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        cleaned = cleaned.replace(",", "")
    elif has_comma:
        comma_parts = cleaned.split(",")
        if len(comma_parts[-1]) in (1, 2):
            cleaned = ".".join(comma_parts)
        else:
            cleaned = "".join(comma_parts)

    try:
        return float(cleaned)
    except ValueError:
        return None


def read_visible_gains(image: Image.Image) -> tuple[pd.DataFrame, bool, str, list[tuple[int, int, int, int]]]:
    if pytesseract is None:
        return pd.DataFrame(columns=["texte_lu", "montant"]), True, "pytesseract n'est pas installe.", []

    try:
        data = pytesseract.image_to_data(image, output_type=Output.DICT, config="--psm 6")
        full_text = pytesseract.image_to_string(image, config="--psm 6")
    except TesseractNotFoundError:
        return (
            pd.DataFrame(columns=["texte_lu", "montant"]),
            True,
            "Le binaire Tesseract OCR est introuvable sur cette machine.",
            [],
        )
    except Exception as exc:
        return pd.DataFrame(columns=["texte_lu", "montant"]), True, f"OCR indisponible : {exc}", []

    amounts = []
    for match in AMOUNT_PATTERN.finditer(full_text):
        raw_value = match.group(0).strip()
        amount = parse_amount(raw_value)
        if amount is not None:
            amounts.append({"texte_lu": raw_value, "montant": amount})

    gain_boxes = []
    confidences = []
    for index, text in enumerate(data.get("text", [])):
        text = str(text).strip()
        if not text or text.lower().endswith("x"):
            continue

        amount = parse_amount(text)
        if amount is None:
            continue

        x = int(data["left"][index])
        y = int(data["top"][index])
        w = int(data["width"][index])
        h = int(data["height"][index])
        gain_boxes.append((x, y, x + w, y + h))

        try:
            confidences.append(float(data["conf"][index]))
        except ValueError:
            confidences.append(-1)

    uncertain = bool(confidences and min(confidences) < 60)
    return pd.DataFrame(amounts, columns=["texte_lu", "montant"]), uncertain, "", gain_boxes


def compute_percentages(blue: int, other: int) -> tuple[int, float, float]:
    total = blue + other
    blue_pct = (blue / total * 100) if total else 0.0
    other_pct = (other / total * 100) if total else 0.0
    return total, blue_pct, other_pct


def most_frequent_message(blue: int, other: int) -> str:
    if blue > other:
        return "Categorie la plus frequente sur l'historique visible : Bleu."
    if other > blue:
        return "Categorie la plus frequente sur l'historique visible : Autres couleurs."
    return "Les deux categories sont equilibrees sur cet historique visible."


def add_debug_rectangles(
    image: Image.Image,
    blue_boxes: list[tuple[int, int, int, int]],
    other_boxes: list[tuple[int, int, int, int]],
    gain_boxes: list[tuple[int, int, int, int]],
) -> Image.Image:
    debug_image = image.copy()
    draw = ImageDraw.Draw(debug_image)

    for box in blue_boxes:
        draw.rectangle(box, outline="#2563eb", width=3)
    for box in other_boxes:
        draw.rectangle(box, outline="#f97316", width=3)
    for box in gain_boxes:
        draw.rectangle(box, outline="#16a34a", width=2)

    return debug_image


def make_distribution_chart(blue: int, other: int):
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(["Bleu", "Autres couleurs"], [blue, other], color=["#2563eb", "#f97316"])
    ax.set_title("Repartition Bleu vs Autres couleurs")
    ax.set_ylabel("Total visible")
    ax.grid(axis="y", alpha=0.2)
    return fig


def make_gain_history_chart(history: list[dict]):
    fig, ax = plt.subplots(figsize=(7, 3))
    if history:
        history_df = pd.DataFrame(history)
        ax.plot(
            history_df["datetime"],
            history_df["somme_gains_visibles"],
            marker="o",
            color="#16a34a",
        )
        ax.tick_params(axis="x", labelrotation=30)
    ax.set_title("Evolution du total des gains visibles par scan")
    ax.set_ylabel("Somme gains visibles")
    ax.grid(alpha=0.2)
    return fig


def analyze_snapshot(
    image: Image.Image,
    hsv_low: tuple[int, int, int],
    hsv_high: tuple[int, int, int],
    min_saturation: int,
    min_value: int,
    min_area: int,
    merge_distance: int,
) -> dict:
    blue_boxes, other_boxes = detect_colored_multipliers(
        image,
        hsv_low,
        hsv_high,
        min_saturation,
        min_value,
        min_area,
        merge_distance,
    )
    gains_df, ocr_uncertain, ocr_error, gain_boxes = read_visible_gains(image)

    blue = len(blue_boxes)
    other = len(other_boxes)
    total, blue_pct, other_pct = compute_percentages(blue, other)

    if gains_df.empty:
        gain_count = 0
        gain_sum = 0.0
        gain_average = 0.0
        biggest_gain = 0.0
    else:
        gain_count = len(gains_df)
        gain_sum = float(gains_df["montant"].sum())
        gain_average = float(gains_df["montant"].mean())
        biggest_gain = float(gains_df["montant"].max())

    return {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "blue": blue,
        "other": other,
        "total": total,
        "blue_pct": blue_pct,
        "other_pct": other_pct,
        "blue_boxes": blue_boxes,
        "other_boxes": other_boxes,
        "gain_boxes": gain_boxes,
        "gains_df": gains_df,
        "ocr_uncertain": ocr_uncertain,
        "ocr_error": ocr_error,
        "gain_count": gain_count,
        "gain_sum": gain_sum,
        "gain_average": gain_average,
        "biggest_gain": biggest_gain,
    }


def store_analysis(image: Image.Image, result: dict) -> None:
    append_history(result)
    st.session_state.last_image = image
    st.session_state.last_result = result
    st.session_state.last_error = ""
    st.session_state.scan_running = False
    st.session_state.url_scan_running = False
    st.session_state.last_analysis_source = "image"


def append_history(result: dict) -> None:
    st.session_state.history.append(
        {
            "datetime": result["datetime"],
            "bleu": result["blue"],
            "autres_couleurs": result["other"],
            "total_tours": result["total"],
            "pourcentage_bleu": round(result["blue_pct"], 2),
            "pourcentage_autres": round(result["other_pct"], 2),
            "nombre_gains_visibles": result["gain_count"],
            "somme_gains_visibles": round(result["gain_sum"], 2),
            "gain_moyen_visible": round(result["gain_average"], 2),
            "plus_gros_gain_visible": round(result["biggest_gain"], 2),
        }
    )


def history_csv(history: list[dict]) -> bytes:
    return pd.DataFrame(history).to_csv(index=False).encode("utf-8")


st.set_page_config(page_title="Crash Live Screen Counter", layout="wide")
init_state()

st.title("Crash Live Screen Counter")
st.info(
    "Cette application analyse seulement les informations visibles publiquement "
    "sur votre ecran. Elle ne se connecte pas au site, n'automatise pas les mises "
    "et ne predit pas le prochain tour."
)

with st.expander("Limites importantes", expanded=True):
    st.markdown(
        """
- L'application ne predit pas le prochain tour.
- Les tours d'un crash game sont normalement independants.
- L'application ne garantit aucun gain.
- Les donnees OCR peuvent contenir des erreurs.
- Elle analyse seulement ce qui est visible sur l'ecran.
- Elle ne doit pas automatiser les paris.
"""
    )

with st.sidebar:
    st.header("Calibration")
    debug_mode = st.checkbox("Mode debug", value=False)

    st.subheader("Bleu HSV")
    hue_min = st.slider("Hue bleu min", 0, 179, 85)
    hue_max = st.slider("Hue bleu max", 0, 179, 135)
    sat_min = st.slider("Saturation bleu min", 0, 255, 60)
    sat_max = st.slider("Saturation bleu max", 0, 255, 255)
    val_min = st.slider("Valeur bleu min", 0, 255, 50)
    val_max = st.slider("Valeur bleu max", 0, 255, 255)

    st.subheader("Sensibilite")
    min_saturation = st.slider("Saturation minimale du texte colore", 0, 255, 45)
    min_value = st.slider("Luminosite minimale du texte colore", 0, 255, 45)
    min_area = st.slider("Surface minimale detectee", 2, 600, 20)
    merge_distance = st.slider("Distance de regroupement", 1, 80, 18)

    st.header("Scan live avance")
    screen_x = st.number_input("x", min_value=0, value=0, step=10)
    screen_y = st.number_input("y", min_value=0, value=0, step=10)
    screen_width = st.number_input("largeur", min_value=50, value=900, step=10)
    screen_height = st.number_input("hauteur", min_value=50, value=500, step=10)
    interval = st.slider("Intervalle de scan (secondes)", 1, 10, 2)

    start_col, stop_col = st.columns(2)
    start_col.button("Demarrer le scan", type="primary", on_click=start_scan)
    stop_col.button("Arreter le scan", on_click=stop_scan)
    st.button("Vider l'historique", on_click=clear_history)

st.header("Mode automatique : scanner depuis une URL")
st.write(
    "Ce mode ouvre la page localement, prend une capture regulierement, puis analyse "
    "ce qui est visible. Il n'automatise aucun clic, aucune connexion et aucune mise."
)

url_value = st.text_input("URL du site", value=DEFAULT_GAME_URL)
url_settings = st.columns(4)
url_interval = url_settings[0].slider("Intervalle URL (secondes)", 1, 15, 3)
url_wait = url_settings[1].slider("Attente chargement (secondes)", 1, 20, 6)
url_width = url_settings[2].number_input("Largeur navigateur", min_value=600, value=1365, step=50)
url_height = url_settings[3].number_input("Hauteur navigateur", min_value=400, value=768, step=50)
url_latest_position = st.selectbox(
    "Ou apparait le dernier tour dans l'historique ?",
    ["Gauche", "Droite", "Haut", "Bas"],
    index=0,
)
url_min_round_gap = st.slider("Temps minimum entre deux tours detectes (secondes)", 2, 20, 6)
show_url_browser = st.checkbox(
    "Afficher le navigateur pour connexion/verifications manuelles",
    value=True,
)

with st.expander("Zone historique URL a analyser", expanded=False):
    st.caption(
        "Si les chiffres semblent faux, reduisez cette zone pour garder seulement la bande "
        "ou les anciens multiplicateurs sont affiches."
    )
    crop_cols = st.columns(4)
    url_crop_left = crop_cols[0].slider("Gauche %", 0, 95, 0)
    url_crop_top = crop_cols[1].slider("Haut %", 0, 95, 0)
    url_crop_width = crop_cols[2].slider("Largeur %", 5, 100, 100)
    url_crop_height = crop_cols[3].slider("Hauteur %", 5, 100, 45)

url_action_cols = st.columns(2)
url_action_cols[0].button(
    "Demarrer l'analyse URL",
    type="primary",
    use_container_width=True,
    on_click=start_url_scan,
)
url_action_cols[1].button(
    "Arreter l'analyse URL",
    use_container_width=True,
    on_click=stop_url_scan,
)

if st.session_state.url_scan_running:
    try:
        full_snapshot = capture_url_page(
            url_value,
            show_url_browser,
            int(url_width),
            int(url_height),
            int(url_wait),
        )
        snapshot = crop_by_percent(
            full_snapshot,
            url_crop_left,
            url_crop_top,
            url_crop_width,
            url_crop_height,
        )
        result = analyze_snapshot(
            snapshot,
            (hue_min, sat_min, val_min),
            (hue_max, sat_max, val_max),
            min_saturation,
            min_value,
            min_area,
            merge_distance,
        )
        previous_session_total = st.session_state.url_session_total
        result, session_message = update_url_session_counter(
            snapshot,
            result,
            url_latest_position,
            url_min_round_gap,
        )
        if result["total"] != previous_session_total:
            append_history(result)
        st.session_state.last_image = snapshot
        st.session_state.last_result = result
        st.session_state.last_error = ""
        st.session_state.last_analysis_source = "url"
        st.info(f"Dernier scan URL : {result['datetime']}")
        if session_message:
            st.warning(session_message)
    except PlaywrightTimeoutError:
        st.session_state.last_error = (
            "La page a mis trop longtemps a charger. Si le site demande une connexion, "
            "activez l'affichage du navigateur, connectez-vous manuellement, puis relancez."
        )
        st.session_state.url_scan_running = False
        close_url_browser()
    except PlaywrightError as exc:
        st.session_state.last_error = (
            "Playwright ne peut pas ouvrir ou capturer la page. "
            "Installez Chromium avec : python -m playwright install chromium. "
            f"Detail : {exc}"
        )
        st.session_state.url_scan_running = False
        close_url_browser()
    except Exception as exc:
        st.session_state.last_error = f"Analyse URL impossible : {exc}"
        st.session_state.url_scan_running = False
        close_url_browser()

st.divider()

st.header("Mode simple : coller une capture")
st.write("Faites `PrtSc` ou `Win + Shift + S`, puis cliquez sur le bouton ci-dessous.")

simple_cols = st.columns([1, 1])
if simple_cols[0].button("Coller depuis le presse-papiers", type="primary", use_container_width=True):
    clipboard_image, clipboard_error = read_clipboard_image()
    if clipboard_error:
        st.session_state.last_error = clipboard_error
        st.session_state.scan_running = False
    elif clipboard_image is not None:
        result = analyze_snapshot(
            clipboard_image,
            (hue_min, sat_min, val_min),
            (hue_max, sat_max, val_max),
            min_saturation,
            min_value,
            min_area,
            merge_distance,
        )
        store_analysis(clipboard_image, result)
        st.success("Capture collee et analysee.")

uploaded_image = simple_cols[1].file_uploader(
    "Ou importer PNG/JPG",
    type=["png", "jpg", "jpeg"],
    label_visibility="collapsed",
)

if uploaded_image is not None and st.button("Analyser l'image importee", use_container_width=True):
    imported_image = Image.open(uploaded_image).convert("RGB")
    result = analyze_snapshot(
        imported_image,
        (hue_min, sat_min, val_min),
        (hue_max, sat_max, val_max),
        min_saturation,
        min_value,
        min_area,
        merge_distance,
    )
    store_analysis(imported_image, result)
    st.success("Image importee et analysee.")

st.divider()

if st.session_state.scan_running:
    try:
        snapshot = capture_screen_region(
            int(screen_x),
            int(screen_y),
            int(screen_width),
            int(screen_height),
        )
        result = analyze_snapshot(
            snapshot,
            (hue_min, sat_min, val_min),
            (hue_max, sat_max, val_max),
            min_saturation,
            min_value,
            min_area,
            merge_distance,
        )
        append_history(result)
        st.session_state.last_image = snapshot
        st.session_state.last_result = result
        st.session_state.last_error = ""
        st.session_state.last_analysis_source = "screen"
    except Exception as exc:
        st.session_state.last_error = f"Scan impossible : {exc}"
        st.session_state.scan_running = False

if st.session_state.last_error:
    st.error(st.session_state.last_error)

scan_state = "actif" if st.session_state.scan_running else "arrete"
url_scan_state = "actif" if st.session_state.url_scan_running else "arrete"
st.caption(f"Etat scan ecran : {scan_state} | Etat analyse URL : {url_scan_state}")

result = st.session_state.last_result
image = st.session_state.last_image

if image is None or result is None:
    st.warning("Collez une capture d'ecran ou importez une image pour commencer.")
else:
    display_image = (
        add_debug_rectangles(
            image,
            result["blue_boxes"],
            result["other_boxes"],
            result["gain_boxes"],
        )
        if debug_mode
        else image
    )

    st.header("Zone scannee")
    st.image(display_image, caption="Derniere capture analysee", use_container_width=True)

    if st.session_state.last_analysis_source == "url":
        st.header("Comptage depuis le demarrage de l'analyse URL")
        st.caption(
            "Le premier scan sert de point de depart. Les nombres augmentent seulement "
            "quand un nouveau tour est detecte apres ce point."
        )
    else:
        st.header("Comptage des couleurs visibles")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Nombre de bleus", result["blue"])
    metric_cols[1].metric("Nombre d'autres couleurs", result["other"])
    metric_cols[2].metric("Total tours visibles", result["total"])
    metric_cols[3].metric("Pourcentage bleu", f"{result['blue_pct']:.2f}%")
    metric_cols[4].metric("Pourcentage autres couleurs", f"{result['other_pct']:.2f}%")

    if st.session_state.last_analysis_source == "url" and st.session_state.url_round_events:
        st.subheader("Tours detectes depuis le demarrage URL")
        events_df = pd.DataFrame(st.session_state.url_round_events[-20:])
        st.dataframe(events_df, use_container_width=True, hide_index=True)

    st.header("Estimation empirique basee sur l'historique visible")
    st.write(f"Bleu : {result['blue_pct']:.2f}%")
    st.write(f"Autres couleurs : {result['other_pct']:.2f}%")
    st.success(most_frequent_message(result["blue"], result["other"]))
    st.warning(
        "Cette estimation est seulement une frequence historique visible. "
        "Elle ne predit pas le prochain tour."
    )

    st.header("Gains visibles")
    gain_cols = st.columns(4)
    gain_cols[0].metric("Nombre de gains visibles", result["gain_count"])
    gain_cols[1].metric("Somme totale des gains visibles", f"{result['gain_sum']:.2f}")
    gain_cols[2].metric("Gain moyen visible", f"{result['gain_average']:.2f}")
    gain_cols[3].metric("Plus gros gain visible", f"{result['biggest_gain']:.2f}")

    if result["ocr_error"]:
        st.warning(result["ocr_error"])
    if result["ocr_uncertain"]:
        st.warning("Lecture OCR a verifier manuellement.")

    if result["gains_df"].empty:
        st.caption("Aucun gain lisible detecte sur cette capture.")
    else:
        st.dataframe(result["gains_df"], use_container_width=True, hide_index=True)

    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        st.pyplot(make_distribution_chart(result["blue"], result["other"]))
    with chart_col_2:
        st.pyplot(make_gain_history_chart(st.session_state.history))

st.header("Historique des scans")
if st.session_state.history:
    history_df = pd.DataFrame(st.session_state.history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Telecharger l'historique en CSV",
        data=history_csv(st.session_state.history),
        file_name="crash_live_screen_counter_history.csv",
        mime="text/csv",
    )
else:
    st.caption("Aucun snapshot enregistre pour le moment.")

if st.session_state.url_scan_running:
    time.sleep(url_interval)
    st.rerun()
elif st.session_state.scan_running:
    time.sleep(interval)
    st.rerun()
