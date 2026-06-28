bl_info = {
    "name": "LLM Sport Addon",
    "author": "Ruryux",
    "version": (1, 1),
    "blender": (5, 1, 2),
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
import os
import csv
from datetime import datetime
from google import genai
from google.genai import types

# ==========================================
# キャッシュ保存用ヘルパー関数
# ==========================================
def save_to_cache(prompt, response_text):
    try:
        # アドオンのフォルダ配下に「llm_sport_cache.csv」という名前で保存します
        cache_file = os.path.join(os.path.dirname(__file__), "llm_sport_cache.csv")
        file_exists = os.path.exists(cache_file)
        
        # 日本語がExcelなどで文字化けしないように utf-8-sig エンコーディングを使用
        with open(cache_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                # 新規作成時にヘッダーを書き出す
                writer.writerow(["Timestamp", "Prompt", "Response"])
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, prompt, response_text])
    except Exception as e:
        print(f"キャッシュCSVの保存に失敗しました: {e}")

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
        answer = response.text
        # キャッシュCSVへの書き出しを実行
        save_to_cache(question, answer)
        return answer
        
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


# スピード検索機能を提供するオペレーター
class LLMSPORT_OT_SpeedSearch(bpy.types.Operator):
    bl_idname = "llmsport.speed_search"
    bl_label = "LLM Sport: スピード検索"
    bl_description = "ホバーしているプロパティ情報を取得してGeminiに質問を送信します"

    @classmethod
    def poll(cls, context):
        # スピード検索がONのときのみ有効
        # pollではhover要素（button_prop等）がまだ存在しない（None）状態なことがあるため、
        # ここでは単純にON/OFFチェックボックスの状態のみを返します。
        return getattr(context.scene, "llm_sport_speed_search_active", False)

    def execute(self, context):
        scene = context.scene
        api_key = scene.llm_sport_api_key

        if not api_key:
            self.report({'WARNING'}, "APIキーが設定されていません。Nパネルで設定してください。")
            bpy.ops.wm.llm_sport_message_box('INVOKE_DEFAULT', message="APIキーが設定されていません。\nNパネルの「LLM Sport」タブでAPIキーを入力してください。")
            return {'FINISHED'}

        prop = getattr(context, "button_prop", None)
        pointer = getattr(context, "button_pointer", None)
        op = getattr(context, "button_operator", None)

        # デバッグ用：取得されたオブジェクトの型をコンソールに表示
        print(f"[LLM Sport Debug] prop: {prop}, pointer: {pointer}, op: {op}")

        question = ""

        if prop:
            prop_name = getattr(prop, "name", "不明") or "不明"
            prop_id = getattr(prop, "identifier", "不明") or "不明"
            prop_desc = getattr(prop, "description", "説明なし") or "説明なし"

            owner_name = "不明"
            if pointer:
                if hasattr(pointer, "name") and pointer.name:
                    owner_name = f"{pointer.rna_type.name} ('{pointer.name}')"
                else:
                    owner_name = pointer.rna_type.name

            prop_value = "取得できませんでした"
            if pointer and prop_id:
                try:
                    val = getattr(pointer, prop_id, None)
                    if val is not None:
                        prop_value = str(val)
                except Exception:
                    pass

            question = (
                f"Blenderのパラメーター「{prop_name}」について教えてください。\n"
                f"・親要素のタイプ: {owner_name}\n"
                f"・内部名 (identifier): {prop_id}\n"
                f"・説明 (description): {prop_desc}\n"
                f"・現在の設定値: {prop_value}\n\n"
                "このパラメーターが何をするものか、また、お勧めの設定値、設定値が高い場合の影響、低い場合の影響を分かりやすく日本語で解説してください。"
            )

        elif op:
            op_name = getattr(op, "name", "不明") or "不明"
            op_id = getattr(op, "bl_idname", "不明") or "不明"
            op_desc = getattr(op, "description", "説明なし") or "説明なし"

            question = (
                f"Blenderの操作・ボタン「{op_name}」について教えてください。\n"
                f"・識別名 (idname): {op_id}\n"
                f"・説明 (description): {op_desc}\n\n"
                "この機能が何をするものか、どのような場面で使うか、および使い方のコツを分かりやすく日本語で解説してください。"
            )

        if not question:
            debug_msg = (
                "ホバーしているプロパティ情報を取得できませんでした。\n\n"
                "【確認・対策】\n"
                "1. 対象のパラメータ（数値スライダー、カラー、チェックボックス等）またはボタンの上に「マウスカーソルが乗っている状態」でEキーを押してください。\n"
                "2. 編集モード中の入力ボックス内（テキスト編集中）ではキーが文字入力として扱われるため、確定させてから（または編集中ではない状態で）ホバーしてEキーを押してください。\n\n"
                f"【デバッグ情報】\n"
                f"- button_prop: {prop}\n"
                f"- button_operator: {op}\n"
                f"- button_pointer: {pointer}"
            )
            self.report({'WARNING'}, "ホバー情報を取得できませんでした。")
            bpy.ops.wm.llm_sport_message_box('INVOKE_DEFAULT', message=debug_msg)
            return {'CANCELLED'}

        # マウスカーソルをローディング（砂時計）にする
        context.window.cursor_set("WAIT")

        # APIの呼び出し
        answer = call_gemini_api(api_key, question)

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
        # 画面中央に幅600ピクセルでダイアログを呼び出す
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        
        # 非常にスマートに長いテキストを複数行に分割して綺麗に表示
        lines = self.message.split('\n')
        
        col = layout.column(align=True)
        for line in lines:
            if not line.strip():
                # 空白行は小さな隙間を空ける
                col.separator()
                continue
                
            # layout.label では幅からはみ出る長い行があるため、
            # 1行あたりの文字数が長い場合は全角/半角を考慮し40文字毎に分割して表示
            if len(line) > 40:
                chunks = [line[i:i+40] for i in range(0, len(line), 40)]
                for chunk in chunks:
                    col.label(text=chunk)
            else:
                col.label(text=line)


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

        # --- スピード検索設定セクション ---
        box_speed = layout.box()
        box_speed.label(text="スピード検索設定", icon='SYSTEM')
        box_speed.prop(scene, "llm_sport_speed_search_active", text="スピード検索機能")
        box_speed.label(text="※ 右クリックメニューから実行可能になります", icon='INFO')

        layout.separator()

        # --- 質問入力セクション ---
        layout.label(text="Blenderの機能を質問する:", icon='QUESTION')
        layout.prop(scene, "llm_sport_question", text="")
        
        # 質問送信ボタン
        layout.operator("llmsport.ask_gemini", text="AIに聞く", icon='PLAY')


# ==========================================
# 4. 登録と解除（__init__.pyに必要な修正）
# ==========================================
# 右クリックメニュー（コンテキストメニュー）に項目を追加する関数
def draw_button_context_menu(self, context):
    # スピード検索がONのときのみ、メニューに表示する
    if getattr(context.scene, "llm_sport_speed_search_active", False):
        self.layout.separator()
        # call_menu などの代わりに直接オペレーターを呼ぶように指定
        # このメニュー内で実行されることで context.button_prop 等が正しく引き継がれます
        self.layout.operator(
            LLMSPORT_OT_SpeedSearch.bl_idname, 
            text="Geminiでスピード検索", 
            icon='QUESTION'
        )

classes = (
    LLMSPORT_OT_AskGemini,
    LLMSPORT_OT_SpeedSearch,
    WM_OT_LLMSportMessageBox,
    VIEW3D_PT_llm_sport_panel,
)

def register():
    # 1. クラスの登録
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # 2. プロパティ（データ入力欄の定義）をBlender of Sceneに登録
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
    bpy.types.Scene.llm_sport_speed_search_active = bpy.props.BoolProperty(
        name="スピード検索",
        description="右クリックメニューに「Geminiでスピード検索」を追加します",
        default=False
    )

    # 3. 右クリックメニューへの追加登録
    bpy.types.UI_MT_button_context_menu.append(draw_button_context_menu)

def unregister():
    # 1. 右クリックメニューの登録解除
    try:
        bpy.types.UI_MT_button_context_menu.remove(draw_button_context_menu)
    except Exception:
        pass

    # 2. クラスの登録解除
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.llm_sport_api_key
    del bpy.types.Scene.llm_sport_question
    del bpy.types.Scene.llm_sport_speed_search_active

if __name__ == "__main__":
    register()
