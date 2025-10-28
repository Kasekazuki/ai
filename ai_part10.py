import gradio as gr
from requests import post
import ast
import re # 正規表現モジュールを追加

def is_valid_python(code: str) -> bool:
    """構文的に正しいPythonコードかをチェック"""
    try:
        # 空のコードは有効としない（または別途処理）
        if not code.strip():
            return False
        ast.parse(code)
        return True
    except SyntaxError:
        return False
    except Exception: # その他のパースエラーも考慮
        return False

def extract_python_code(text: str) -> str:
    """LLMの出力からPythonコードブロックを抽出する"""
    # ```python ... ``` または ``` ... ``` の形式を優先
    match_code_block = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match_code_block:
        return match_code_block.group(1).strip()

    match_code_block = re.search(r"```\n(.*?)```", text, re.DOTALL)
    if match_code_block:
        return match_code_block.group(1).strip()
    
    # コードブロックがない場合、そのまま返す（ただし、後のis_valid_pythonでチェックされる）
    return text.strip()

def fix_code(input_code):
    # まず構文的に正しいかチェック
    initial_needs_fix = not is_valid_python(input_code)

    prompt = (
        "あなたはPythonコードの修正アシスタントです。"
        "次のコードを確認し、構文エラーや論理エラーがある場合のみ修正版コードを出力してください。"
        "もし問題がなければ、『✅ 正常に実行できます』とだけ返してください。\n\n"
        "【重要】修正が必要な場合、**余計な説明やコメントを一切含めず、純粋な完成したPythonコードのみをマークダウン形式のコードブロック（```python\n...\n```）で出力してください。**\n"
        "もし修正不要な場合、他のテキストを含めず『✅ 正常に実行できます』とだけ出力してください。\n\n"
        f"入力コード:\n```python\n{input_code}\n```\n\n"
        "修正または判定結果:"
    )

    try:
        response = post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma:2b", "prompt": prompt, "stream": False, "options": {"temperature": 0.0}} # temperatureを低めに設定
        )
        response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる

        data = response.json()
        raw_output = data.get("response") or data.get("output") or ""

    except Exception as e:
        return f"⚠️ Ollama APIエラーが発生しました: {e}"

    # LLMの出力からコード部分を抽出
    extracted_code = extract_python_code(raw_output)

    # --- 出力が空またはNoneの場合の処理 ---
    if not raw_output.strip():
        return "⚠️ AIからの応答がありませんでした。"

    # --- 構文チェックとAIの応答判断 ---
    if initial_needs_fix:
        # 修正版が正しいPythonコードなら採用
        if is_valid_python(extracted_code):
            return extracted_code
        else:
            return f"⚠️ 修正が必要ですが、AIが正しく修正できませんでした。\n\nAIの応答:\n{raw_output}"
    else:
        # 修正不要のとき
        if raw_output.strip() == "✅ 正常に実行できます":
            return "✅ 正常に実行できます"
        elif is_valid_python(extracted_code):
            # AIがなぜかコードを返した場合（本来は不要な場合）
            # ここではAIが修正不要と判断せずコードを返したとみなし、そのコードが有効なら採用
            return extracted_code
        else:
            return f"⚠️ 予期しない出力が発生しました。修正は不要と判断されましたが、AIの出力が不明確です。\n\nAIの応答:\n{raw_output}"

# --- Gradio UI設定 ---
ui = gr.Interface(
    fn=fix_code,
    inputs=gr.Textbox(lines=15, label="修正したいコードを入力", placeholder="例:\nfor num in range(1, 101):\n    if num % 3 == 0 and num % 5 == 0;\n        print(\"FizzBuzz\")"),
    outputs=gr.Textbox(lines=15, label="修正結果（Output）", placeholder="ここに結果が表示されます"),
    title="CodeFixAI - Gemma",
    description="Gemma（Ollama）を使ったローカルコード修正AI（構文チェック付き）"
)

ui.launch()