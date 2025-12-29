import sys
import os
import asyncio
import aiohttp
import aiofiles
import json
from functools import partial

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QLabel,
                             QListWidget, QListWidgetItem, QSlider, QCheckBox,
                             QDialog, QMenu, QFileDialog, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QSettings
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import QIcon, QPixmap, QAction, QCursor


# ==========================================
# 核心逻辑
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


BG_PATH = resource_path("音乐下载器/img/壁纸.png")
ICON_PATH = resource_path("音乐下载器/ico/miao_64x64.ico")
# 预留空状态插画路径 (你需要自己放一张图在这里，或者用代码里的默认文字)
EMPTY_STATE_IMG = resource_path("音乐下载器/img/empty_state.png")


async def page_parm(kw):
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "referer": "https://musicjx.com/",
        "x-requested-with": "XMLHttpRequest"
    }
    datas = {"input": kw, "filter": "name", "type": "netease", "page": "1"}
    return headers, datas


async def is_valid_audio(session, item, headers):
    url = item.get("url", "")
    if not url: return None
    try:
        async with session.head(url, headers=headers, timeout=2, allow_redirects=True) as res:
            content_type = res.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type: return None
            if res.status != 200: return None
            return item
    except:
        return None


async def fetch_music_data(kw):
    main_url = 'https://musicjx.com/'
    headers, datas = await page_parm(kw)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(main_url, headers=headers, data=datas) as res:
                if res.status != 200: return None
                response_text = await res.text()
                url_lists = json.loads(response_text)
                raw_data_list = []
                if "data" in url_lists:
                    for item in url_lists["data"][1:]:
                        raw_data_list.append({
                            "title": item.get("title", "未知歌曲"),
                            "author": item.get("author", "未知歌手"),
                            "url": item.get("url", "")
                        })
                tasks = [is_valid_audio(session, item, headers) for item in raw_data_list]
                results = await asyncio.gather(*tasks)
                valid_data_list = [item for item in results if item is not None]
                return valid_data_list
        except Exception as e:
            print(f"搜索出错: {e}")
            return None


# 修改：增加 save_dir 参数
async def download_single_music(url, filename, headers, save_dir):
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    file_path = os.path.join(save_dir, filename)
    headers["upgrade-insecure-requests"] = "1"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, allow_redirects=True) as res:
                content_type = res.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type: return False
                if res.status == 200:
                    async with aiofiles.open(file_path, mode='wb') as fp:
                        await fp.write(await res.read())
                    return True
        except:
            pass
    return False


# ==========================================
# 线程类
# ==========================================

class SearchThread(QThread):
    finished_signal = pyqtSignal(list)

    def __init__(self, keyword):
        super().__init__()
        self.keyword = keyword

    def run(self):
        result = asyncio.run(fetch_music_data(self.keyword))
        if result is not None: self.finished_signal.emit(result)


class BatchDownloadThread(QThread):
    all_finished = pyqtSignal(int, int)
    progress_signal = pyqtSignal(int)  # 新增进度信号 (百分比)

    def __init__(self, tasks, save_path):
        super().__init__()
        self.tasks = tasks
        self.save_path = save_path  # 接收动态路径

    def run(self):
        success_count = 0
        fail_count = 0
        total = len(self.tasks)

        async def _batch_do():
            nonlocal success_count, fail_count
            headers, _ = await page_parm("")
            for i, (idx, url, fname) in enumerate(self.tasks):
                # 传入 save_path
                res = await download_single_music(url, fname, headers, self.save_path)
                if res:
                    success_count += 1
                else:
                    fail_count += 1

                # 计算并发送进度 (i+1) / total * 100
                progress = int(((i + 1) / total) * 100)
                self.progress_signal.emit(progress)

            self.all_finished.emit(success_count, fail_count)

        asyncio.run(_batch_do())


# ==========================================
# 自定义组件：萌系弹窗
# ==========================================
class CuteMessageBox(QDialog):
    def __init__(self, parent, success_count, fail_count, save_path):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(320, 240)

        layout = QVBoxLayout(self)
        self.container = QWidget()
        self.container.setObjectName("MsgBoxContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_lbl = QLabel()
        pixmap = QIcon(ICON_PATH).pixmap(QSize(60, 60))
        self.icon_lbl.setPixmap(pixmap)
        container_layout.addWidget(self.icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_lbl = QLabel("捕捉任务收官! 🐾")
        self.title_lbl.setStyleSheet("font-size: 18px; color: #ff7f7f; font-weight: bold; margin-top: 5px;")
        container_layout.addWidget(self.title_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        content = f"已入库信号: {success_count} 条\n丢包/干扰: {fail_count} 条"
        self.content_lbl = QLabel(content)
        self.content_lbl.setStyleSheet("font-size: 14px; color: #555; margin: 5px;")
        self.content_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.content_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # 显示保存路径提示
        path_short = save_path if len(save_path) < 20 else "..." + save_path[-20:]
        self.path_lbl = QLabel(f"保存在: {path_short}")
        self.path_lbl.setStyleSheet("font-size: 11px; color: #999; margin-bottom: 10px;")
        container_layout.addWidget(self.path_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_ok = QPushButton("收录完毕")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.setFixedSize(120, 35)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setStyleSheet("""
            QPushButton { background-color: #ff7f7f; color: white; border-radius: 17px; font-weight: bold; }
            QPushButton:hover { background-color: #ff9999; }
        """)
        container_layout.addWidget(self.btn_ok, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.container)
        self.setStyleSheet(
            """QWidget#MsgBoxContainer { background-color: white; border: 3px solid #ffb3b3; border-radius: 20px; }""")


# ==========================================
# UI 界面
# ==========================================

class MusicApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("猫耳下载器")  # 更新版本号
        self.resize(1050, 680)
        self.setWindowIcon(QIcon(ICON_PATH))

        # --- 1. 初始化设置 (保存路径) ---
        self.settings = QSettings("MyTeam", "CatMusicApp")
        # 默认路径
        default_path = os.path.join(os.getcwd(), "music_downloaded")
        self.download_path = self.settings.value("download_path", default_path)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5)

        self.init_ui()
        self.apply_styles()
        self.update_empty_state()  # 初始化空状态

        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)

    def init_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        # --- 顶部功能区 (搜索 + 设置 + 关于) ---
        top_container = QWidget()
        top_container.setObjectName("TopContainer")
        top_layout = QHBoxLayout(top_container)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("输入歌名搜索...")
        self.input_search.returnPressed.connect(self.start_search)

        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.start_search)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear_results)

        # 新增：设置按钮
        self.btn_settings = QPushButton("⚙️ 设置路径")
        self.btn_settings.setStyleSheet("background-color: #88ccff;")
        self.btn_settings.clicked.connect(self.select_download_folder)

        # 新增：关于按钮
        self.btn_about = QPushButton("ℹ️ 关于")
        self.btn_about.setStyleSheet("background-color: #ffcc88;")
        self.btn_about.clicked.connect(self.show_disclaimer)

        top_layout.addWidget(QLabel("歌曲搜索:"))
        top_layout.addWidget(self.input_search)
        top_layout.addWidget(self.btn_search)
        top_layout.addWidget(self.btn_clear)
        top_layout.addWidget(self.btn_settings)  # 添加到布局
        top_layout.addWidget(self.btn_about)  # 添加到布局

        layout.addWidget(top_container)

        # 批量操作区
        batch_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("全选 / 取消")
        self.btn_select_all.setObjectName("BatchBtn")
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        self.btn_download_selected = QPushButton("下载选中内容")
        self.btn_download_selected.setObjectName("BatchBtn")
        self.btn_download_selected.clicked.connect(self.start_batch_download)
        batch_layout.addWidget(self.btn_select_all)
        batch_layout.addStretch()
        batch_layout.addWidget(self.btn_download_selected)
        layout.addLayout(batch_layout)

        # --- 结果展示区 (包含空状态) ---
        # StackLayout 或者 简单的覆盖逻辑，这里用简单的显隐逻辑
        self.list_area_widget = QWidget()
        list_area_layout = QVBoxLayout(self.list_area_widget)
        list_area_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 正常列表
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 开启右键菜单
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        list_area_layout.addWidget(self.list_widget)

        # 2. 空状态提示 (默认隐藏)
        self.empty_state_lbl = QLabel()
        self.empty_state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_lbl.setStyleSheet(
            "color: #666; font-size: 16px; background: rgba(255,255,255,0.6); border-radius: 10px;")
        list_area_layout.addWidget(self.empty_state_lbl)

        layout.addWidget(self.list_area_widget)

        # 播放器控制区
        self.player_container = QWidget()
        self.player_container.setObjectName("PlayerContainer")
        player_main_layout = QVBoxLayout(self.player_container)

        player_header_layout = QHBoxLayout()
        self.lbl_now_playing = QLabel("未在播放")
        self.lbl_now_playing.setStyleSheet("font-size: 13px; color: #444;")
        self.btn_close_player = QPushButton("×")
        self.btn_close_player.setObjectName("ClosePlayerBtn")
        self.btn_close_player.setFixedSize(30, 30)
        self.btn_close_player.clicked.connect(self.hide_player)
        player_header_layout.addWidget(self.lbl_now_playing)
        player_header_layout.addStretch()
        player_header_layout.addWidget(self.btn_close_player)
        player_main_layout.addLayout(player_header_layout)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.sliderReleased.connect(self.set_position)
        player_main_layout.addWidget(self.progress_slider)

        ctrl_layout = QHBoxLayout()
        self.btn_play_pause = QPushButton("暂停")
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)

        ctrl_layout.addWidget(self.btn_play_pause)
        ctrl_layout.addWidget(self.lbl_time)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("音量:"))
        ctrl_layout.addWidget(self.volume_slider)
        player_main_layout.addLayout(ctrl_layout)

        layout.addWidget(self.player_container)
        self.player_container.setVisible(False)

        # --- 底部状态与进度条 ---
        status_layout = QHBoxLayout()

        # 新增：下载进度条
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setTextVisible(True)
        self.download_progress.setFixedWidth(200)
        self.download_progress.setVisible(False)  # 默认隐藏，下载时显示
        # 进度条样式
        self.download_progress.setStyleSheet("""
            QProgressBar { border: 1px solid #ff7f7f; border-radius: 5px; text-align: center; color: black; }
            QProgressBar::chunk { background-color: #ff7f7f; }
        """)

        self.status_label = QLabel("🎧 猫耳已就位，随时监听信号...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        status_layout.addWidget(self.download_progress)
        status_layout.addStretch()
        status_layout.addWidget(self.status_label)
        layout.addLayout(status_layout)

        self.all_selected = False

    def apply_styles(self):
        bg_path_css = BG_PATH.replace('\\', '/')
        style = f"""
        QWidget#CentralWidget {{ border-image: url("{bg_path_css}") 0 0 0 0 stretch stretch; }}
        QWidget#TopContainer, QWidget#PlayerContainer {{ 
            background-color: rgba(255, 255, 255, 0.85); 
            border-radius: 12px; padding: 10px; 
        }}
        QCheckBox {{ spacing: 8px; color: white; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid white; border-radius: 3px; background: rgba(255, 255, 255, 0.1); }}
        QCheckBox::indicator:checked {{ background-color: #ff7f7f; }}
        QLabel {{ font-size: 14px; color: #333; font-weight: bold; }}
        QLineEdit {{ padding: 8px; border-radius: 5px; background: white; border: 1px solid #ff7f7f; }}
        QPushButton {{ padding: 8px 15px; border-radius: 6px; color: white; background-color: #ff7f7f; font-weight: bold; }}
        QPushButton#ClosePlayerBtn {{ background: transparent; color: #ff7f7f; font-size: 20px; padding: 0; }}
        QPushButton#ClosePlayerBtn:hover {{ color: #ff3333; }}
        QListWidget {{ background-color: rgba(30, 30, 30, 0.6); border-radius: 10px; outline: none; border: 1px solid rgba(255,255,255,0.2); }}
        QListWidget::item {{ border-bottom: 1px solid rgba(255, 255, 255, 0.1); }}
        QLabel#ItemTitle {{ font-size: 15px; color: #ffffff; padding: 2px; }}
        QPushButton#ItemPlayBtn {{ background: transparent; color: rgba(255,255,255,0.9); font-size: 22px; padding: 0 5px; }}
        QPushButton#ItemPlayBtn:hover {{ color: #ff7f7f; }}
        """
        self.setStyleSheet(style)

    # ================= 新功能实现 =================

    # 1. 设置下载路径
    def select_download_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择猫耳音频文件的存储仓库", self.download_path)
        if folder:
            self.download_path = folder
            # 保存到配置
            self.settings.setValue("download_path", self.download_path)
            self.status_label.setText(f"📁 窝搬家啦: {self.download_path}")

    # 2. 空状态管理
    def update_empty_state(self):
        has_items = self.list_widget.count() > 0
        self.list_widget.setVisible(has_items)
        self.empty_state_lbl.setVisible(not has_items)

        if not has_items:
            # 这里加载图片，如果图片不存在则显示文字
            if os.path.exists(EMPTY_STATE_IMG):
                pix = QPixmap(EMPTY_STATE_IMG).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                self.empty_state_lbl.setPixmap(pix)
            else:
                # 默认萌系文字
                self.empty_state_lbl.setText("🐾 猫耳空空...附近没有可捕捉的信号。\n\n换个频率（关键词）试试？\n或者只是想发呆喵？")

    # 3. 法律与合规性弹窗
    def show_disclaimer(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("关于猫耳下载器")
        msg.setIconPixmap(QIcon(ICON_PATH).pixmap(64, 64))
        text = (
            "<h3>🎧 猫耳下载器 (CatEar Downloader) v1.1</h3>"
            "<p>猫耳是一款专注于高灵敏音频信号嗅探与收录的轻量化工具。</p>"
            "<hr>"
            "<p><b>📻 频率使用守则 (免责声明)：</b></p>"
            "<ul style='font-size:12px;'>"
            "<li><b>信号来源：</b>本工具通过公开频率接口进行信号模拟，不存储任何资源。</li>"
            "<li><b>学术用途：</b>仅供无线电频谱（Python & 网络请求）技术交流使用。</li>"
            "<li><b>版权保护：</b>请尊重每一段旋律的版权。收录后请于24小时内清除信号。</li>"
            "</ul>"
            "<p style='color:#ff7f7f; font-weight:bold;'>🐾 只要有旋律，猫耳就能听见。</p>"
        )
        msg.setText(text)
        msg.exec()

    # 4. 右键菜单
    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return

        menu = QMenu(self)
        # 获取真实数据
        url = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)

        # 动作1: 复制歌名
        action_copy_name = QAction("📄 复制歌名", self)
        action_copy_name.triggered.connect(lambda: QApplication.clipboard().setText(name))
        menu.addAction(action_copy_name)

        # 动作2: 复制链接
        action_copy_url = QAction("🔗 提取频率地址", self)
        action_copy_url.triggered.connect(lambda: QApplication.clipboard().setText(url))
        menu.addAction(action_copy_url)

        menu.exec(QCursor.pos())

    # ================= 原有逻辑修改 =================

    def start_search(self):
        kw = self.input_search.text().strip()
        if not kw: return
        self.status_label.setText("📡 猫耳正在全力捕捉音频频率... ( •̀ ω •́ )y")
        self.list_widget.clear()
        self.update_empty_state()  # 刷新状态

        self.search_thread = SearchThread(kw)
        self.search_thread.finished_signal.connect(self.on_search_finished)
        self.search_thread.start()

    def on_search_finished(self, data_list):
        self.status_label.setText(f"✨ 成功解调出 {len(data_list)} 束音频信号！快来挑选吧~")
        for data in data_list:
            name = f"{data['title']} - {data['author']}"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, data['url'])
            item.setData(Qt.ItemDataRole.UserRole + 1, name)

            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(15, 12, 15, 12)
            cb = QCheckBox()
            layout.addWidget(cb)
            lbl = QLabel(name)
            lbl.setObjectName("ItemTitle")
            lbl.setWordWrap(True)
            layout.addWidget(lbl, 1)
            play_btn = QPushButton("▶")
            play_btn.setObjectName("ItemPlayBtn")
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.clicked.connect(partial(self.play_specific_music, data['url'], name + ".mp3"))
            layout.addWidget(play_btn)

            self.list_widget.addItem(item)
            item.setSizeHint(container.sizeHint())
            self.list_widget.setItemWidget(item, container)

        self.update_empty_state()  # 搜索完检查是否为空

    def start_batch_download(self):
        tasks = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            cb = w.findChild(QCheckBox)
            if cb and cb.isChecked():
                tasks.append((i, item.data(Qt.ItemDataRole.UserRole), item.data(Qt.ItemDataRole.UserRole + 1) + ".mp3"))
        if not tasks:
            self.status_label.setText("⚠ 尚未锁定信号源，请勾选音轨！")
            return

        self.status_label.setText("🚀 正在高速传输音频数据流... 📶")
        self.btn_download_selected.setEnabled(False)

        # 显示并重置进度条
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)

        # 传递 self.download_path (用户设置的路径)
        self.batch_thread = BatchDownloadThread(tasks, self.download_path)
        self.batch_thread.all_finished.connect(self.on_batch_finished)
        self.batch_thread.progress_signal.connect(self.download_progress.setValue)  # 连接进度信号
        self.batch_thread.start()

    def on_batch_finished(self, s, f):
        self.btn_download_selected.setEnabled(True)
        self.download_progress.setVisible(False)  # 隐藏进度条
        self.status_label.setText("✅ 信号收录完毕，数据同步成功！")

        # 传递路径给弹窗
        msg_box = CuteMessageBox(self, s, f, self.download_path)
        msg_box.exec()

    def clear_results(self):
        self.list_widget.clear()
        self.input_search.clear()
        self.hide_player()
        self.update_empty_state()
        self.status_label.setText("🧹 信号已清除，回归寂静。")

    # ... (保持原有的播放器控制函数不变: hide_player, play_specific_music, toggle_playback, set_volume 等) ...
    def hide_player(self):
        self.media_player.stop()
        self.player_container.setVisible(False)

    def play_specific_music(self, url, filename):
        if not url: return
        self.player_container.setVisible(True)
        self.lbl_now_playing.setText(f"🎶 正在解析音频流: {filename}")
        self.media_player.stop()
        self.media_player.setSource(QUrl(url))
        self.media_player.play()
        self.btn_play_pause.setText("暂停")

    def toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play_pause.setText("播放")
        else:
            self.media_player.play()
            self.btn_play_pause.setText("暂停")

    def stop_playback(self):
        self.media_player.stop()
        self.btn_play_pause.setText("播放")

    def set_volume(self, value):
        self.audio_output.setVolume(value / 100)

    def update_position(self, pos):
        if not self.progress_slider.isSliderDown():
            self.progress_slider.setValue(pos)
        self.update_time_label(pos, self.media_player.duration())

    def update_duration(self, dur):
        self.progress_slider.setRange(0, dur)

    def set_position(self):
        self.media_player.setPosition(self.progress_slider.value())

    def update_time_label(self, curr, total):
        cm, cs = divmod(curr // 1000, 60)
        tm, ts = divmod(total // 1000, 60)
        self.lbl_time.setText(f"{cm:02}:{cs:02} / {tm:02}:{ts:02}")

    def toggle_select_all(self):
        self.all_selected = not self.all_selected
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            cb = w.findChild(QCheckBox)
            if cb: cb.setChecked(self.all_selected)


if __name__ == '__main__':
    import ctypes

    myappid = 'myteam.musicdownloader.catversion.1.1'  # 更新版本号
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication(sys.argv)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    window = MusicApp()
    window.show()
    sys.exit(app.exec())