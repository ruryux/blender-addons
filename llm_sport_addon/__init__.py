bl_info = {
    "name": "LLM Sport Addon",
    "author": "Your Name",
    "version": (1, 1),
    "blender": (4, 2, 0),  # お使いのバージョンに合わせてください
    "location": "View3D > Sidebar > LLM Sport Tab",
    "description": "NパネルからGemini Flash APIを呼び出し、簡潔な回答を中央ポップアップで表示するアドオン",
    "category": "Development",
}

import subprocess
import sys
import importlib


# 依存ライブラリの自動インストール
def ensure_dependencies():
    try:
        # すでにインストールされているかチェック
        importlib.import_module("google.genai")
    except ImportError:
        print("google-genai を検出できませんでした。インストールを開始します...")
        # Blenderの内蔵Pythonのパスを取得してpipを実行
        py_exec = sys.executable
        try:
            subprocess.check_call([py_exec, "-m", "pip", "install", "google-genai"])
            print("google-genai のインストールが完了しました。")
        except Exception as e:
            print(f"インストールの自動実行に失敗しました: {e}")

# クラス登録の前に実行
ensure_dependencies()


import bpy
from google import genai
from google.genai import types

# ==========================================
# 1. API通信ロジック (Gemini 1.5 Flash)
# ==========================================
def call_gemini_api(api_key, question):
    try:
        # クライアントの初期化
        client = genai.Client(api_key=api_key)
        
        # 正しいメソッドと引数の構成
        response = client.models.generate_content(
            model='gemini-2.5-flash',  # 2.5 Flash（または gemini-1.5-flash）を指定
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "あなたはBlenderの専門家です。基本的には要点を絞って3行以内の非常に簡潔かつ完結な日本語で答えてください。\n"
                    "ただし、ユーザーが設定値やパラメータについて尋ねてきた場合は、以下の3点を確実に含めて5行以内で簡潔に回答してください：\n"
                    "1. お勧めの設定値\n"
                    "2. 設定値が高い（大きい）場合の影響・挙動\n"
                    "3. 設定値が低い（小さい）場合の影響・挙動"
                )
            )
        )
        return response.text
        
    except Exception as e:
        # エラー内容をBlenderのコンソルやポップアップで見やすく整形
        return f"SDKエラーが発生しました:\n{str(e)}"


# ==========================================
# 2. オペレーター（実行処理＆中央ポップアップ）
# ==========================================

# 質問を実行してメッセージボックスを呼び出すオペレーター
class LLMSPORT_OT_AskGemini(bpy.types.Operator):
    bl_idname = "llmsport.ask_gemini"
    bl_label = "Geminiに質問を送信"
    bl_description = "入力された質問をGemini 1.5 Flashに送信し、回答を中央に表示します"

    def execute(self, context):
        scene = context.scene

        # マウスカーソルをローディング（砂時計）にする
        context.window.cursor_set("WAIT")

        # APIの呼び出し
        answer = call_gemini_api(scene.llm_sport_api_key, scene.llm_sport_question)

        # マウスカーソルを元に戻す
        context.window.cursor_set("DEFAULT")

        # 中央ポップアップ表示用オペレーターを呼び出し、回答を渡す
        bpy.ops.wm.llm_sport_message_box('INVOKE_DEFAULT', message=answer)
        return {'FINISHED'}


# 画面中央にダイアログ（ポップアップ）を表示するオペレーター
class WM_OT_LLMSportMessageBox(bpy.types.Operator):
    bl_idname = "wm.llm_sport_message_box"
    bl_label = "LLM Sport: 回答"
    
    message: bpy.props.StringProperty()

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        # 画面中央に幅500ピクセルでダイアログを呼び出す
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        
        # テキストが長い場合に備え、改行コードで分割して1行ずつ描画
        lines = self.message.split('\n')
        for line in lines:
            if line.strip() or line == "":
                layout.label(text=line)


# ==========================================
# 3. UI パネル（Nメニューの見た目）
# ==========================================
class VIEW3D_PT_llm_sport_panel(bpy.types.Panel):
    bl_label = "LLM Sport"
    bl_idname = "VIEW3D_PT_llm_sport_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LLM Sport'  # Nキーのタブ名

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- API設定セクション ---
        box = layout.box()
        box.label(text="API 設定", icon='PREFERENCES')
        box.prop(scene, "llm_sport_api_key", text="APIキー")

        layout.separator()

        # --- 質問入力セクション ---
        layout.label(text="Blenderの機能を質問する:", icon='QUESTION')
        layout.prop(scene, "llm_sport_question", text="")
        
        # 質問送信ボタン
        layout.operator("llmsport.ask_gemini", text="AIに聞く", icon='PLAY')


# ==========================================
# 4. 登録と解除（__init__.pyに必要な修正）
# ==========================================
classes = (
    LLMSPORT_OT_AskGemini,
    WM_OT_LLMSportMessageBox,
    VIEW3D_PT_llm_sport_panel,
)

def register():
    # 1. クラスの登録
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # 2. プロパティ（データ入力欄の定義）をBlenderのSceneに登録
    # これにより、APIキーや質問内容がBlender内部に保持されます
    bpy.types.Scene.llm_sport_api_key = bpy.props.StringProperty(
        name="API Key",
        description="Google AI Studioで取得したAPIキーを入力してください",
        default="",
        subtype='PASSWORD'
    )
    bpy.types.Scene.llm_sport_question = bpy.props.StringProperty(
        name="Question",
        description="わからない機能を日本語で入力してください",
        default="スマートキーフレームの使い方について教えて"
    )

def unregister():
    # 登録解除
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.llm_sport_api_key
    del bpy.types.Scene.llm_sport_question

if __name__ == "__main__":
    register()