import sys
import base64
import requests
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QPushButton, QMessageBox, QDialog,
    QSpinBox, QFormLayout, QCheckBox, QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# 配置文件路径
CONFIG_PATH = "ocr_config.json"
# 高级设置默认值
DEFAULT_ADVANCED_SETTINGS = {
    # 通用识别参数
    "general": {
        "min_size": 16,
        "max_size": 1000,
        "language_type": "zh_en",
        "rotate": False,
        "accuracy": "normal"
    },
    # 手写体识别参数
    "handwriting": {
        "min_size": 16,
        "max_size": 1000,
        "rotate": 0,
        "table": True,
        "line_number": 0,
        "confidence_threshold": 0.5,
        "language_type": "zh_en"
    }
}

# ====================== 识别线程（核心逻辑） ======================
class OCRThread(QThread):
    result_signal = pyqtSignal(str)

    def __init__(self, image_path, ocr_type, appcode, advanced_settings):
        super().__init__()
        self.image_path = image_path
        self.ocr_type = ocr_type  # "general" 或 "handwriting"
        self.appcode = appcode
        self.advanced_settings = advanced_settings  # 高级设置参数

    def run(self):
        try:
            # 1. 读取图片
            try:
                with open(self.image_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                self.result_signal.emit(f"图片读取失败：{str(e)}")
                return

            # 2. 选择接口URL和配置
            if self.ocr_type == "general":
                ocr_url = "https://tysbgpu.market.alicloudapi.com/api/predict/ocr_general"
                # 构建通用识别配置
                configure = {
                    "min_size": self.advanced_settings["min_size"],
                    "max_size": self.advanced_settings["max_size"],
                    "LanguageType": self.advanced_settings["language_type"],
                    "rotate": self.advanced_settings["rotate"],
                    "accuracy": self.advanced_settings["accuracy"]
                }
                body = {"image": img_base64, "configure": configure}
            else:
                ocr_url = "https://shouxiegen.market.alicloudapi.com/ocrservice/shouxie"
                # 构建手写体识别配置
                configure = {
                    "Handwriting": True,
                    "Table": self.advanced_settings["table"],
                    "min_size": self.advanced_settings["min_size"],
                    "max_size": self.advanced_settings["max_size"],
                    "rotate": self.advanced_settings["rotate"],
                    "LineNumber": self.advanced_settings["line_number"],
                    "ConfidenceThreshold": self.advanced_settings["confidence_threshold"],
                    "LanguageType": self.advanced_settings["language_type"]
                }
                body = {"img": img_base64, "configure": configure}

            # 3. 发送请求
            headers = {
                "Authorization": f"APPCODE {self.appcode}",
                "Content-Type": "application/json"
            }

            response = requests.post(ocr_url, json=body, headers=headers, timeout=30)
            response.raise_for_status()
            result_json = response.json()

            # 4. 解析结果
            if self.ocr_type == "general":
                # 通用识别结果解析
                result_text = ""
                if "ret" in result_json and isinstance(result_json["ret"], list):
                    word_list = []
                    for item in result_json["ret"]:
                        if isinstance(item, dict) and "word" in item:
                            word_list.append(item["word"])
                    result_text = "\n".join(word_list)
                    
                    if not result_text:
                        result_text = f"未提取到文字内容，原始响应：\n{json.dumps(result_json, ensure_ascii=False, indent=2)}"
                else:
                    result_text = f"识别结果格式异常：\n{json.dumps(result_json, ensure_ascii=False, indent=2)}"
                
                self.result_signal.emit(result_text)
            else:
                # 手写识别结果解析
                self.result_signal.emit(result_json.get("content", "手写识别成功但无内容"))

        except requests.exceptions.Timeout:
            self.result_signal.emit("识别超时（请压缩图片或检查网络）")
        except requests.exceptions.ConnectionError:
            self.result_signal.emit("网络错误（无法连接接口）")
        except requests.exceptions.HTTPError as e:
            if "401" in str(e):
                self.result_signal.emit("AppCode无效或过期（请重新输入）")
            elif "400" in str(e):
                self.result_signal.emit(f"参数错误：{str(e)}\n可能是图片格式或大小不符合要求")
            else:
                self.result_signal.emit(f"接口错误：{str(e)}")
        except Exception as e:
            self.result_signal.emit(f"识别失败：{str(e)}")


# ====================== 高级设置对话框 ======================
class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent=None, ocr_type="general", current_settings=None):
        super().__init__(parent)
        self.ocr_type = ocr_type
        # 初始化设置（使用当前设置或默认值）
        if current_settings:
            self.settings = current_settings.copy()
        else:
            self.settings = DEFAULT_ADVANCED_SETTINGS[self.ocr_type].copy()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"高级设置 - {'通用识别' if self.ocr_type == 'general' else '手写体识别'}")
        self.setMinimumWidth(400)
        layout = QFormLayout()
        
        # 语言选择
        self.language_combo = QComboBox()
        self.language_combo.addItems(["zh_en（中英文）", "zh（中文）", "en（英文）", "ja（日文）", "ko（韩文）"])
        # 设置当前语言
        lang_index = self.language_combo.findText(f"{self.settings['language_type']}")
        if lang_index >= 0:
            self.language_combo.setCurrentIndex(lang_index)
        layout.addRow(QLabel("识别语言："), self.language_combo)
        
        # 最小文字大小
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(8, 100)
        self.min_size_spin.setValue(self.settings["min_size"])
        self.min_size_spin.setToolTip("识别的最小文字像素尺寸")
        layout.addRow(QLabel("最小文字大小："), self.min_size_spin)
        
        # 最大文字大小
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(100, 2000)
        self.max_size_spin.setValue(self.settings["max_size"])
        self.max_size_spin.setToolTip("识别的最大文字像素尺寸")
        layout.addRow(QLabel("最大文字大小："), self.max_size_spin)
        
        # 根据识别类型添加不同参数
        if self.ocr_type == "general":
            # 通用识别特有参数
            self.rotate_check = QCheckBox("自动旋转校正")
            self.rotate_check.setChecked(self.settings["rotate"])
            layout.addRow(QLabel("图片处理："), self.rotate_check)
            
            self.accuracy_combo = QComboBox()
            self.accuracy_combo.addItems(["normal（普通精度）", "high（高精度）"])
            acc_index = self.accuracy_combo.findText(f"{self.settings['accuracy']}")
            if acc_index >= 0:
                self.accuracy_combo.setCurrentIndex(acc_index)
            layout.addRow(QLabel("识别精度："), self.accuracy_combo)
            
        else:
            # 手写体识别特有参数
            self.rotate_spin = QSpinBox()
            self.rotate_spin.setRange(-180, 180)
            self.rotate_spin.setValue(self.settings["rotate"])
            self.rotate_spin.setToolTip("手动设置文字旋转角度")
            layout.addRow(QLabel("旋转角度："), self.rotate_spin)
            
            self.table_check = QCheckBox("启用表格识别")
            self.table_check.setChecked(self.settings["table"])
            layout.addRow(QLabel("表格处理："), self.table_check)
            
            self.line_number_spin = QSpinBox()
            self.line_number_spin.setRange(0, 100)
            self.line_number_spin.setValue(self.settings["line_number"])
            self.line_number_spin.setToolTip("0表示自动检测行数")
            layout.addRow(QLabel("预期行数："), self.line_number_spin)
            
            self.confidence_spin = QDoubleSpinBox()
            self.confidence_spin.setRange(0.1, 1.0)
            self.confidence_spin.setSingleStep(0.1)
            self.confidence_spin.setValue(self.settings["confidence_threshold"])
            self.confidence_spin.setToolTip("识别置信度阈值，低于此值的结果会被过滤")
            layout.addRow(QLabel("置信度阈值："), self.confidence_spin)
        
        # 确认按钮
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        # 总布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
    
    def get_settings(self):
        """获取用户设置的参数"""
        settings = {
            "language_type": self.language_combo.currentText().split("（")[0],
            "min_size": self.min_size_spin.value(),
            "max_size": self.max_size_spin.value()
        }
        
        if self.ocr_type == "general":
            settings.update({
                "rotate": self.rotate_check.isChecked(),
                "accuracy": self.accuracy_combo.currentText().split("（")[0]
            })
        else:
            settings.update({
                "rotate": self.rotate_spin.value(),
                "table": self.table_check.isChecked(),
                "line_number": self.line_number_spin.value(),
                "confidence_threshold": self.confidence_spin.value()
            })
            
        return settings


# ====================== 主界面 ======================
class OCRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.load_config()
        # 初始化高级设置
        self.advanced_settings = DEFAULT_ADVANCED_SETTINGS.copy()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("OCR识别工具（通用/手写切换）")
        self.resize(800, 600)
        self.setFont(QFont("微软雅黑", 10))

        # 主布局
        main_layout = QVBoxLayout()

        # 1. 识别模式选择
        mode_layout = QHBoxLayout()
        mode_label = QLabel("识别模式：", self)
        self.mode_group = QButtonGroup(self)
        self.general_radio = QRadioButton("通用识别（印刷体/表格）", self)
        self.hand_radio = QRadioButton("手写体识别", self)
        self.general_radio.setChecked(True)
        self.mode_group.addButton(self.general_radio, 1)
        self.mode_group.addButton(self.hand_radio, 2)
        self.mode_group.idToggled.connect(self.on_mode_change)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.general_radio)
        mode_layout.addWidget(self.hand_radio)
        main_layout.addLayout(mode_layout)

        # 2. AppCode输入和高级设置按钮
        top_controls_layout = QHBoxLayout()
        
        appcode_layout = QHBoxLayout()
        self.appcode_label = QLabel("通用识别AppCode：", self)
        self.appcode_input = QLineEdit(self)
        self.appcode_input.setPlaceholderText("请输入阿里云AppCode...")
        self.save_btn = QPushButton("保存配置", self)
        self.save_btn.clicked.connect(self.save_config)
        appcode_layout.addWidget(self.appcode_label)
        appcode_layout.addWidget(self.appcode_input)
        appcode_layout.addWidget(self.save_btn)
        
        # 高级设置按钮
        self.advanced_btn = QPushButton("高级设置")
        self.advanced_btn.clicked.connect(self.show_advanced_settings)
        
        top_controls_layout.addLayout(appcode_layout, 3)
        top_controls_layout.addWidget(self.advanced_btn, 1)
        main_layout.addLayout(top_controls_layout)

        # 3. 拖放区域
        self.drop_label = QLabel("👇 拖放图片到这里 👇", self)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setStyleSheet("""
            border: 2px dashed #ccc; 
            padding: 40px; 
            border-radius: 8px;
            font-size: 16px;
            color: #666;
        """)
        self.drop_label.setAcceptDrops(True)
        main_layout.addWidget(self.drop_label)

        # 4. 结果显示
        result_label = QLabel("识别结果：", self)
        self.result_edit = QTextEdit(self)
        self.result_edit.setReadOnly(False)
        main_layout.addWidget(result_label)
        main_layout.addWidget(self.result_edit)

        self.setLayout(main_layout)
        self.setAcceptDrops(True)
        self.update_appcode_input()

    # 切换识别模式
    def on_mode_change(self, radio_id, is_checked):
        if is_checked:
            if radio_id == 1:  # 通用模式
                self.appcode_label.setText("通用识别AppCode：")
                self.appcode_input.setText(self.config.get("general_appcode", ""))
            else:  # 手写模式
                self.appcode_label.setText("手写体识别AppCode：")
                self.appcode_input.setText(self.config.get("hand_appcode", ""))

    # 显示高级设置对话框
    def show_advanced_settings(self):
        # 获取当前识别模式
        ocr_type = "general" if self.general_radio.isChecked() else "handwriting"
        # 显示对话框
        dialog = AdvancedSettingsDialog(self, ocr_type, self.advanced_settings[ocr_type])
        if dialog.exec_() == QDialog.Accepted:
            # 保存用户设置的参数
            self.advanced_settings[ocr_type] = dialog.get_settings()
            QMessageBox.information(self, "提示", "高级设置已保存！")

    # 拖放事件处理
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_label.setStyleSheet("""
                border: 2px dashed #007bff; 
                padding: 40px; 
                border-radius: 8px;
                font-size: 16px;
                color: #007bff;
            """)

    def dragLeaveEvent(self, event):
        self.drop_label.setStyleSheet("""
            border: 2px dashed #ccc; 
            padding: 40px; 
            border-radius: 8px;
            font-size: 16px;
            color: #666;
        """)

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        file_urls = event.mimeData().urls()
        if not file_urls:
            return
        image_path = file_urls[0].toLocalFile()
        self.drop_label.setText(f"识别中：{image_path.split('/')[-1]}...")
        self.result_edit.clear()

        ocr_type = "general" if self.general_radio.isChecked() else "handwriting"
        appcode = self.appcode_input.text().strip()
        if not appcode:
            QMessageBox.warning(self, "提示", "请先输入AppCode并保存！")
            self.drop_label.setText("👇 拖放图片到这里 👇")
            return

        # 启动识别线程，传入高级设置参数
        self.ocr_thread = OCRThread(
            image_path, 
            ocr_type, 
            appcode, 
            self.advanced_settings[ocr_type]
        )
        self.ocr_thread.result_signal.connect(self.show_result)
        self.ocr_thread.start()

    # 显示结果
    def show_result(self, result):
        self.drop_label.setText("👇 拖放图片到这里 👇")
        self.result_edit.setText(result)

    # 配置保存与加载
    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except:
            self.config = {"general_appcode": "", "hand_appcode": ""}

    def update_appcode_input(self):
        if self.general_radio.isChecked():
            self.appcode_input.setText(self.config.get("general_appcode", ""))
        else:
            self.appcode_input.setText(self.config.get("hand_appcode", ""))

    def save_config(self):
        appcode = self.appcode_input.text().strip()
        if not appcode:
            QMessageBox.warning(self, "提示", "AppCode不能为空！")
            return
        if self.general_radio.isChecked():
            self.config["general_appcode"] = appcode
        else:
            self.config["hand_appcode"] = appcode
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False)
        QMessageBox.information(self, "提示", "配置保存成功！")


# ====================== 运行程序 ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec_())
