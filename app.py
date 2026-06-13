import time
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).with_name(".matplotlib")))

import cv2
import matplotlib.pyplot as plt
import mss
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw


APP_NAME = "Crash Live Counter"
ESTIMATION_MESSAGE = (
    "Cette estimation est une frequence historique basee sur les donnees deja enregistrees. "
    "Elle ne predit pas le prochain tour."
)


def init_state() -> None:
    defaults = {
        "scan_running": False,
        "current_result": None,
        "current_image": None,
        "current_debug_image": None,
        "current_signature": "",
        "last_added_signature": "",
        "history": [],
        "scan_counter": 0,
        "manual_blue": 0,
        "manual_other": 0,
        "last_error": "",
        "last_add_message": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def capture_screen_region(x: int, y: int, width: int, height: int) -> Image.Image:
    monitor = {"left": x, "top": y, "width": width, "height": height}
    with mss.MSS() as sct:
        screenshot = sct.grab(monitor)

    frame = np.array(screenshot)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    return Image.fromarray(rgb_frame)


def preprocess_image(
    image: Image.Image,
    min_saturation: int,
    min_value: int,
    dark_background_value: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.array(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    colored_mask = cv2.inRange(
        hsv,
        np.array((0, min_saturation, min_value)),
        np.array((179, 255, 255)),
    )
    dark_mask = cv2.inRange(hsv[:, :, 2], 0, dark_background_value)
    mask = cv2.bitwise_and(colored_mask, cv2.dilate(dark_mask, np.ones((5, 5), np.uint8)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    return rgb, hsv, mask


def merge_boxes(
    boxes: list[tuple[int, int, int, int]],
    merge_distance: int,
) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        current = box
        changed = True
        while changed:
            changed = False
            remaining = []
            for other in merged:
                x_gap = max(0, max(current[0], other[0]) - min(current[2], other[2]))
                y_gap = max(0, max(current[1], other[1]) - min(current[3], other[3]))
                same_line = min(current[3], other[3]) >= max(current[1], other[1]) - merge_distance
                same_column = min(current[2], other[2]) >= max(current[0], other[0]) - merge_distance
                if (x_gap <= merge_distance and same_line) or (y_gap <= merge_distance and same_column):
                    current = (
                        min(current[0], other[0]),
                        min(current[1], other[1]),
                        max(current[2], other[2]),
                        max(current[3], other[3]),
                    )
                    changed = True
                else:
                    remaining.append(other)
            merged = remaining
        merged.append(current)
    return sorted(merged, key=lambda item: (item[1], item[0]))


def classify_block_color(
    hsv: np.ndarray,
    box: tuple[int, int, int, int],
    blue_low: tuple[int, int, int],
    blue_high: tuple[int, int, int],
    min_saturation: int,
    min_value: int,
) -> str:
    x1, y1, x2, y2 = box
    block = hsv[y1:y2, x1:x2]
    if block.size == 0:
        return "other"

    colored_mask = cv2.inRange(
        block,
        np.array((0, min_saturation, min_value)),
        np.array((179, 255, 255)),
    )
    blue_mask = cv2.inRange(block, np.array(blue_low), np.array(blue_high))
    colored_pixels = int(np.count_nonzero(colored_mask))
    blue_pixels = int(np.count_nonzero(blue_mask))
    if colored_pixels == 0:
        return "other"
    return "blue" if blue_pixels / colored_pixels >= 0.45 else "other"


def detect_colored_text_blocks(
    image: Image.Image,
    blue_low: tuple[int, int, int],
    blue_high: tuple[int, int, int],
    min_saturation: int,
    min_value: int,
    dark_background_value: int,
    min_area: int,
    max_area: int,
    min_width: int,
    max_width: int,
    min_height: int,
    max_height: int,
    merge_distance: int,
) -> list[dict]:
    _, hsv, mask = preprocess_image(image, min_saturation, min_value, dark_background_value)
    components_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    raw_boxes = []

    for label in range(1, components_count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue
        if width < min_width or width > max_width:
            continue
        if height < min_height or height > max_height:
            continue
        raw_boxes.append((x, y, x + width, y + height))

    merged_boxes = merge_boxes(raw_boxes, merge_distance)
    blocks = []
    for box in merged_boxes:
        width = box[2] - box[0]
        height = box[3] - box[1]
        area = width * height
        aspect_ratio = width / max(height, 1)

        if area < min_area or area > max_area:
            continue
        if width < min_width or width > max_width:
            continue
        if height < min_height or height > max_height:
            continue
        if width > image.width * 0.22 or height > image.height * 0.45:
            continue
        if not 0.35 <= aspect_ratio <= 8.5:
            continue

        color = classify_block_color(hsv, box, blue_low, blue_high, min_saturation, min_value)
        blocks.append({"box": box, "color": color})

    return blocks


def compute_stats(blue: int, other: int) -> dict:
    total = blue + other
    blue_pct = (blue / total * 100) if total else 0.0
    other_pct = (other / total * 100) if total else 0.0
    return {
        "blue": blue,
        "other": other,
        "total": total,
        "blue_pct": blue_pct,
        "other_pct": other_pct,
    }


def make_scan_signature(blocks: list[dict]) -> str:
    parts = []
    for block in sorted(blocks, key=lambda item: (item["box"][1], item["box"][0], item["color"])):
        x1, y1, x2, y2 = block["box"]
        parts.append(f"{block['color']}:{x1//8}:{y1//8}:{(x2-x1)//4}:{(y2-y1)//4}")
    return "|".join(parts) if parts else "empty"


def build_result(source: str, image: Image.Image, blocks: list[dict]) -> dict:
    blue = sum(1 for block in blocks if block["color"] == "blue")
    other = sum(1 for block in blocks if block["color"] != "blue")
    stats = compute_stats(blue, other)
    stats.update(
        {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "blocks": blocks,
            "signature": make_scan_signature(blocks),
            "image_size": image.size,
        }
    )
    return stats


def add_scan_to_history(result: dict) -> bool:
    signature = result.get("signature", "")
    if result.get("total", 0) == 0:
        return False
    if signature == st.session_state.last_added_signature:
        return False

    st.session_state.scan_counter += 1
    entry = {
        "scan_id": st.session_state.scan_counter,
        "datetime": result["datetime"],
        "source": result["source"],
        "bleu": result["blue"],
        "autres_couleurs": result["other"],
        "total": result["total"],
        "pourcentage_bleu": round(result["blue_pct"], 2),
        "pourcentage_autres": round(result["other_pct"], 2),
        "signature": signature,
    }
    st.session_state.history.append(entry)
    st.session_state.last_added_signature = signature
    return True


def reset_current_scan() -> None:
    st.session_state.current_result = None
    st.session_state.current_image = None
    st.session_state.current_debug_image = None
    st.session_state.current_signature = ""
    st.session_state.last_error = ""
    st.session_state.last_add_message = ""


def reset_global_history() -> None:
    st.session_state.history = []
    st.session_state.scan_counter = 0
    st.session_state.last_added_signature = ""
    st.session_state.last_add_message = "Cumul global reinitialise."


def compute_global_stats() -> dict:
    blue = sum(int(row["bleu"]) for row in st.session_state.history)
    other = sum(int(row["autres_couleurs"]) for row in st.session_state.history)
    return compute_stats(blue, other)


def draw_debug_boxes(image: Image.Image, blocks: list[dict]) -> Image.Image:
    debug = image.copy()
    draw = ImageDraw.Draw(debug)
    for block in blocks:
        color = "#38bdf8" if block["color"] == "blue" else "#f472b6"
        draw.rectangle(block["box"], outline=color, width=3)
    return debug


def render_stat_cards(title: str, stats: dict) -> None:
    st.markdown(f"### {title}")
    cols = st.columns(5)
    cols[0].metric("Bleu", stats["blue"])
    cols[1].metric("Autres couleurs", stats["other"])
    cols[2].metric("Total", stats["total"])
    cols[3].metric("% Bleu", f"{stats['blue_pct']:.2f}%")
    cols[4].metric("% Autres", f"{stats['other_pct']:.2f}%")


def make_bar_chart(title: str, blue: int, other: int):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")
    ax.bar(["Bleu", "Autres"], [blue, other], color=["#38bdf8", "#f472b6"])
    ax.set_title(title, color="#f9fafb")
    ax.tick_params(colors="#e5e7eb")
    ax.spines["bottom"].set_color("#374151")
    ax.spines["left"].set_color("#374151")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#374151", alpha=0.45)
    return fig


def render_charts(current_stats: dict, global_stats: dict) -> None:
    left, right = st.columns(2)
    left.pyplot(make_bar_chart("Repartition scan actuel", current_stats["blue"], current_stats["other"]))
    right.pyplot(make_bar_chart("Repartition cumul global", global_stats["blue"], global_stats["other"]))


def export_history_csv() -> bytes:
    columns = [
        "scan_id",
        "datetime",
        "source",
        "bleu",
        "autres_couleurs",
        "total",
        "pourcentage_bleu",
        "pourcentage_autres",
    ]
    if not st.session_state.history:
        return pd.DataFrame(columns=columns).to_csv(index=False).encode("utf-8")
    return pd.DataFrame(st.session_state.history)[columns].to_csv(index=False).encode("utf-8")


def analyze_image(source: str, image: Image.Image, settings: dict) -> dict:
    blocks = detect_colored_text_blocks(
        image,
        settings["blue_low"],
        settings["blue_high"],
        settings["min_saturation"],
        settings["min_value"],
        settings["dark_background_value"],
        settings["min_area"],
        settings["max_area"],
        settings["min_width"],
        settings["max_width"],
        settings["min_height"],
        settings["max_height"],
        settings["merge_distance"],
    )
    result = build_result(source, image, blocks)
    st.session_state.current_result = result
    st.session_state.current_image = image
    st.session_state.current_debug_image = draw_debug_boxes(image, blocks)
    st.session_state.current_signature = result["signature"]
    st.session_state.last_error = ""
    return result


def dominant_category(stats: dict) -> str:
    if stats["blue"] > stats["other"]:
        return "Bleu"
    if stats["other"] > stats["blue"]:
        return "Autres couleurs"
    return "Equilibre"


st.set_page_config(page_title=APP_NAME, page_icon="CL", layout="wide")
init_state()

st.markdown(
    """
    <style>
    .stApp { background: #0b1020; color: #f8fafc; }
    [data-testid="stSidebar"] { background: #111827; }
    [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #263244;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
    }
    .section-card {
        background: #111827;
        border: 1px solid #263244;
        border-radius: 8px;
        padding: 16px;
        margin: 12px 0;
    }
    .muted { color: #94a3b8; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Reglages")
    mode = st.radio("Mode", ["Scan ecran local", "Manuel"])
    debug_mode = st.checkbox("Mode debug", value=True)
    st.caption("Le cumul global change seulement quand vous cliquez sur `Ajouter ce scan au cumul`.")

    st.divider()
    st.subheader("HSV bleu")
    hue_min = st.slider("Hue bleu min", 0, 179, 85)
    hue_max = st.slider("Hue bleu max", 0, 179, 135)
    blue_sat_min = st.slider("Saturation bleu min", 0, 255, 60)
    blue_val_min = st.slider("Valeur bleu min", 0, 255, 50)

    st.subheader("Detection texte colore")
    min_saturation = st.slider("Saturation minimale", 0, 255, 45)
    min_value = st.slider("Luminosite minimale", 0, 255, 45)
    dark_background_value = st.slider("Fond sombre max", 0, 255, 95)
    min_area = st.slider("Surface min contour", 1, 500, 8)
    max_area = st.slider("Surface max contour", 20, 5000, 1200)
    min_width = st.slider("Largeur min bloc", 1, 80, 3)
    max_width = st.slider("Largeur max bloc", 10, 300, 90)
    min_height = st.slider("Hauteur min bloc", 1, 80, 3)
    max_height = st.slider("Hauteur max bloc", 5, 120, 28)
    merge_distance = st.slider("Distance regroupement", 1, 80, 10)

settings = {
    "blue_low": (hue_min, blue_sat_min, blue_val_min),
    "blue_high": (hue_max, 255, 255),
    "min_saturation": min_saturation,
    "min_value": min_value,
    "dark_background_value": dark_background_value,
    "min_area": min_area,
    "max_area": max_area,
    "min_width": min_width,
    "max_width": max_width,
    "min_height": min_height,
    "max_height": max_height,
    "merge_distance": merge_distance,
}

st.title(APP_NAME)
st.caption("Analyse statistique des couleurs visibles")
st.warning(
    "Cette application analyse seulement des resultats passes visibles ou deja enregistres. "
    "Elle ne predit pas le prochain tour, ne propose aucune strategie de mise et ne gere pas d'argent reel."
)
st.info(
    "Mode principal : ouvrez Aviator vous-meme dans votre navigateur, placez l'historique des "
    "multiplicateurs bien visible, puis choisissez la zone exacte a scanner."
)
st.warning("Reglez x, y, largeur, hauteur pour encadrer uniquement la boite HISTORIQUE DE LA MANCHE.")

current_stats = st.session_state.current_result or compute_stats(0, 0)
global_stats = compute_global_stats()

if mode == "Scan ecran local":
    st.markdown("### Mode principal - Scan ecran local")
    st.caption(
        "L'application capture directement la zone visible de votre ecran avec mss. "
        "Elle n'ouvre aucune URL et n'utilise pas Playwright. Ne cadrez pas le logo, le menu, "
        "l'heure, les boutons de pari ou le graphique principal."
    )
    scan_cols = st.columns(5)
    screen_x = scan_cols[0].number_input("x", min_value=0, value=0, step=10)
    screen_y = scan_cols[1].number_input("y", min_value=0, value=0, step=10)
    screen_width = scan_cols[2].number_input("largeur", min_value=50, value=900, step=10)
    screen_height = scan_cols[3].number_input("hauteur", min_value=50, value=500, step=10)
    scan_interval = scan_cols[4].slider("intervalle", 1, 10, 2)

    test_col, start_col, stop_col = st.columns(3)
    if test_col.button("Tester la zone", use_container_width=True):
        try:
            image = capture_screen_region(int(screen_x), int(screen_y), int(screen_width), int(screen_height))
            analyze_image("Test zone", image, settings)
            st.success("Zone testee. Verifiez l'apercu ci-dessous avant de demarrer le scan.")
        except Exception as exc:
            st.session_state.last_error = f"Test de zone impossible : {exc}"

    if start_col.button("Demarrer scan", type="primary", use_container_width=True):
        st.session_state.scan_running = True
    if stop_col.button("Arreter scan", use_container_width=True):
        st.session_state.scan_running = False

    if st.session_state.scan_running:
        try:
            image = capture_screen_region(int(screen_x), int(screen_y), int(screen_width), int(screen_height))
            result = analyze_image("Scan ecran", image, settings)
        except Exception as exc:
            st.session_state.last_error = f"Scan ecran impossible : {exc}"
            st.session_state.scan_running = False

elif mode == "Manuel":
    st.markdown("### Mode manuel de secours")
    st.caption("Utilisez ce mode si l'analyse automatique ne lit pas correctement l'historique visible.")
    manual_cols = st.columns(5)
    if manual_cols[0].button("+1 Bleu", use_container_width=True):
        st.session_state.manual_blue += 1
    if manual_cols[1].button("-1 Bleu", use_container_width=True):
        st.session_state.manual_blue = max(0, st.session_state.manual_blue - 1)
    if manual_cols[2].button("+1 Autres couleurs", use_container_width=True):
        st.session_state.manual_other += 1
    if manual_cols[3].button("-1 Autres couleurs", use_container_width=True):
        st.session_state.manual_other = max(0, st.session_state.manual_other - 1)
    if manual_cols[4].button("Reset", use_container_width=True):
        st.session_state.manual_blue = 0
        st.session_state.manual_other = 0

    manual_stats = compute_stats(st.session_state.manual_blue, st.session_state.manual_other)
    manual_stats.update(
        {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "Manuel",
            "blocks": [],
            "signature": f"manual:{st.session_state.manual_blue}:{st.session_state.manual_other}",
            "image_size": (0, 0),
        }
    )
    st.session_state.current_result = manual_stats
    st.session_state.current_signature = manual_stats["signature"]
    st.session_state.current_image = None
    st.session_state.current_debug_image = None
    current_stats = manual_stats
    if st.button("Ajouter le manuel au cumul", type="primary", use_container_width=True):
        if add_scan_to_history(manual_stats):
            st.session_state.last_add_message = "Saisie manuelle ajoutee au cumul."
        else:
            st.session_state.last_add_message = "Saisie manuelle vide ou identique a la derniere entree."
        st.rerun()

if st.session_state.last_error:
    st.error(st.session_state.last_error)

current_stats = st.session_state.current_result or compute_stats(0, 0)
global_stats = compute_global_stats()
signature_changed = bool(st.session_state.current_signature) and (
    st.session_state.current_signature != st.session_state.last_added_signature
)

st.divider()
render_stat_cards("Statistiques du scan actuel", current_stats)
render_stat_cards("Cumul global depuis le lancement", global_stats)

manual_add_cols = st.columns([1, 1, 2])
if manual_add_cols[0].button("Ajouter ce scan au cumul", type="primary", use_container_width=True):
    if st.session_state.current_result:
        added = add_scan_to_history(st.session_state.current_result)
        st.session_state.last_add_message = (
            "Scan ajoute au cumul." if added else "Scan vide ou identique au dernier scan ajoute."
        )
        st.rerun()
    else:
        st.warning("Aucun scan actuel a ajouter.")
manual_add_cols[1].metric("Nouveau scan detecte", "Oui" if signature_changed else "Non")
reset_cols = st.columns(2)
if reset_cols[0].button("Reinitialiser scan actuel", use_container_width=True):
    reset_current_scan()
    st.rerun()
if reset_cols[1].button("Reinitialiser cumul global", use_container_width=True):
    reset_global_history()
    st.rerun()

if st.session_state.last_add_message:
    st.info(st.session_state.last_add_message)

st.markdown("### Zone analysee")
if st.session_state.current_image is None:
    st.info("Aucune capture analysee pour le moment.")
else:
    image_to_show = st.session_state.current_debug_image if debug_mode else st.session_state.current_image
    block_count = len(st.session_state.current_result.get("blocks", [])) if st.session_state.current_result else 0
    st.metric("Blocs detectes dans la zone", block_count)
    st.image(image_to_show, caption="Derniere capture analysee", use_container_width=True)

st.markdown("### Graphiques")
render_charts(current_stats, global_stats)

st.markdown("### Estimation empirique basee sur l'historique")
est_cols = st.columns(3)
est_cols[0].metric("Bleu global", f"{global_stats['blue_pct']:.2f}%")
est_cols[1].metric("Autres couleurs global", f"{global_stats['other_pct']:.2f}%")
est_cols[2].metric("Categorie dominante historique", dominant_category(global_stats))
st.warning(ESTIMATION_MESSAGE)

st.markdown("### Historique enregistre")
history_cols = st.columns(3)
if history_cols[0].button("Supprimer derniere entree", use_container_width=True):
    if st.session_state.history:
        st.session_state.history.pop()
        st.session_state.last_added_signature = (
            st.session_state.history[-1]["signature"] if st.session_state.history else ""
        )
        st.rerun()
if history_cols[1].button("Vider historique", use_container_width=True):
    reset_global_history()
    st.rerun()
history_cols[2].download_button(
    "Exporter CSV",
    data=export_history_csv(),
    file_name=f"crash-live-counter-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
    mime="text/csv",
    use_container_width=True,
)

if st.session_state.history:
    history_df = pd.DataFrame(st.session_state.history).drop(columns=["signature"], errors="ignore")
    st.dataframe(history_df, use_container_width=True, hide_index=True)
else:
    st.info("Aucun scan enregistre dans le cumul.")

if mode == "Scan ecran local" and st.session_state.scan_running:
    time.sleep(int(scan_interval))
    st.rerun()
