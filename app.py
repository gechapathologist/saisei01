"""
再生問題フォーマッター
複数教員から回収した穴埋め問題を統一フォーマットに整形する
"""

from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

# 空欄として認識するパターン（様々な形式に対応）
BLANK_PATTERNS = [
    r'（\s*）',                          # （　）全角括弧
    r'\(\s*\)',                          # ( ) 半角括弧
    r'【\s*】',                          # 【　】
    r'\[\s*\]',                          # [ ]
    r'_{2,}',                            # __ アンダースコア2つ以上
    r'＿{2,}',                           # ＿＿ 全角アンダースコア2つ以上
    r'[（(]\s*[ABab]\s*[）)]',           # (A) （B） (a) (b) など括弧付きアルファベット
    r'（\s*[①②]\s*）',                  # （①）（②）丸数字
    r'\(\s*[①②]\s*\)',                  # (①) (②) 丸数字半角括弧
    r'（\s*[12]\s*）',                   # （1）（2）数字
    r'\(\s*[12]\s*\)',                   # (1) (2) 数字半角括弧
]

# ですます調→である調の変換パターン
DESU_MASU_PATTERNS = [
    (r'でしょうか', 'であろうか'),
    (r'ましょう', 'よう'),
    (r'ません', 'ない'),
    (r'ました', 'た'),
    (r'ています', 'ている'),
    (r'てきます', 'てくる'),
    (r'ております', 'ている'),
    (r'されています', 'されている'),
    (r'なっています', 'なっている'),
    (r'います', 'いる'),
    (r'あります', 'ある'),
    (r'きます', 'くる'),
    (r'します', 'する'),
    (r'ですが', 'であるが'),
    (r'ですので', 'であるので'),
    (r'ですから', 'であるから'),
    (r'です', 'である'),
    (r'ます', 'る'),
]

# 疑問文末尾の統一パターン（「なにか。」に統一）
QUESTION_END_PATTERNS = [
    (r'は何でしょうか[。？?]?', 'はなにか。'),
    (r'は何ですか[。？?]?', 'はなにか。'),
    (r'は何であろうか[。？?]?', 'はなにか。'),
    (r'は何であるか[。？?]?', 'はなにか。'),
    (r'は何か[。？?]?', 'はなにか。'),
    (r'はなんでしょうか[。？?]?', 'はなにか。'),
    (r'はなんですか[。？?]?', 'はなにか。'),
    (r'はなんであろうか[。？?]?', 'はなにか。'),
    (r'はなんであるか[。？?]?', 'はなにか。'),
    (r'はなんか[。？?]?', 'はなにか。'),
]

def normalize_standalone_letters(text):
    """
    日本語文中の単独アルファベット（A, B, C...）を空欄マーカーに変換
    
    以下のパターンを検出：
    - 日本語の後に単独大文字アルファベット + 日本語/句読点が続く場合
    - 例: "〜はAである" → "〜は{{BLANK}}である"
    - 例: "A、B、Cの方法" → "{{BLANK}}、{{BLANK}}、{{BLANK}}の方法"
    
    以下は変換しない：
    - 英単語の一部（前後にアルファベットがある）
    - 「A型」「B細胞」など、アルファベット+漢字/カタカナの複合語
    """
    # 日本語文字（ひらがな、カタカナ、漢字）
    jp_char = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
    
    result = text
    
    # 除外パターン（アルファベット+特定の漢字/カタカナ）
    # これらは固有名詞や専門用語として扱う
    exclude_suffixes = r'型|群|細胞|抗原|受容体|リンパ球|ウイルス|遺伝子|タンパク|蛋白|因子|鎖|座|領域|ドメイン|クラス|サブ|波|線|層|帯|管|点|面|軸|端|相|期|染色体'
    
    # 除外する前の文字パターン（「T細胞」「B細胞」のように前に特定文字がない場合）
    # T, Bなど単独で使われる専門用語のアルファベット
    exclude_letters_before_cell = {'T', 'B', 'K', 'NK'}
    
    # 「T細胞」「B細胞」などの専門用語を先に保護
    for letter in exclude_letters_before_cell:
        result = re.sub(f'{letter}(細胞|リンパ球|抗原|受容体)', f'__PROTECT_{letter}_\\1__', result)
    
    # パターン1: 日本語 + 大文字アルファベット1文字 + 除外接尾辞
    # これらは変換しない（先に保護）
    def protect_technical_terms(match):
        return f'__TECH_{match.group(1)}_{match.group(2)}__'
    
    tech_pattern = f'({jp_char})([A-Z])({exclude_suffixes})'
    result = re.sub(tech_pattern, lambda m: m.group(1) + f'__TECH_{m.group(2)}__' + m.group(3), result)
    
    # パターン2: 日本語/句読点/接続詞 + 大文字アルファベット1文字 + 日本語/句読点/接続詞
    # ただし、前後に他のアルファベットがある場合は除外（英単語の一部）
    #
    # 対象文字:
    # - 前: 日本語、読点、接続詞（と、や、・）
    # - 後: 日本語、読点、接続詞
    before_chars = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF、,とや・]'
    after_chars = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF、,とや・など]'
    
    def replace_standalone(match):
        before = match.group(1)
        letter = match.group(2)
        after = match.group(3)
        return before + '{{BLANK}}' + after
    
    # 繰り返し適用（A、B、Cのような連続パターンに対応）
    prev_result = None
    while prev_result != result:
        prev_result = result
        pattern = f'({before_chars})([A-Z])({after_chars})'
        result = re.sub(pattern, replace_standalone, result)
    
    # 保護した専門用語を復元
    result = re.sub(r'__TECH_([A-Z])__', r'\1', result)
    for letter in exclude_letters_before_cell:
        result = re.sub(f'__PROTECT_{letter}_(.+?)__', f'{letter}\\1', result)
    
    # 保護した専門用語を復元
    for letter in exclude_letters_before_cell:
        result = re.sub(f'__PROTECT_{letter}_(.+?)__', f'{letter}\\1', result)
    
    return result

def normalize_blanks(text):
    """様々な形式の空欄を統一マーカーに変換"""
    result = text
    
    # まず従来のパターンで変換
    for pattern in BLANK_PATTERNS:
        result = re.sub(pattern, '{{BLANK}}', result)
    
    # 次に単独アルファベットを変換
    result = normalize_standalone_letters(result)
    
    return result

def convert_desu_masu(text):
    """ですます調をである調に変換し、疑問文末尾を統一"""
    result = text
    # まず疑問文末尾を統一（先に処理しないと「何ですか」→「何であるか」になってしまう）
    for pattern, replacement in QUESTION_END_PATTERNS:
        result = re.sub(pattern, replacement, result)
    # ですます調→である調
    for pattern, replacement in DESU_MASU_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result

def clean_text(text):
    """余計な空白や句読点を整理"""
    # Markdown太字記法を除去 **text** → text
    result = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Markdown斜体記法を除去 *text* → text
    result = re.sub(r'\*(.+?)\*', r'\1', result)
    # カンマ+句点の重複を除去
    result = re.sub(r',。', '。', result)
    result = re.sub(r'、。', '。', result)
    result = re.sub(r',.', '.', result)
    result = re.sub(r',、', '、', result)
    # 連続する空白を1つに
    result = re.sub(r'[ 　]+', ' ', result)
    # 連続する句読点を1つに
    result = re.sub(r'[、，]+', '、', result)
    result = re.sub(r'[。．]+', '。', result)
    # 文頭・文末の空白を除去
    result = result.strip()
    # 改行の整理
    result = re.sub(r'\n\s*\n', '\n', result)
    return result

def format_blanks(text, blank_count):
    """空欄マーカーを適切な形式に変換"""
    if blank_count == 0:
        return text
    elif blank_count == 1:
        # 空欄1つの場合：ラベルなし
        return text.replace('{{BLANK}}', '（　　　　　）')
    else:
        # 空欄2つ以上の場合：A, B, C... のラベル付き
        labels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = text
        for i in range(blank_count):
            if i < len(labels):
                result = result.replace('{{BLANK}}', f'（　　{labels[i]}　　）', 1)
        return result

def format_answer(answer, blank_count):
    """正解を適切な形式に整形"""
    answer = answer.strip()
    
    if blank_count == 0:
        # 空欄なしの場合はそのまま
        return f'正解：{answer}' if answer else '正解：'
    elif blank_count == 1:
        # 空欄1つの場合
        # 既に「正解：」が含まれていれば除去
        answer = re.sub(r'^正解[：:]\s*', '', answer)
        return f'正解：{answer}'
    else:
        # 空欄2つ以上の場合
        # 既存のフォーマットを解析して整形
        answer = re.sub(r'^正解[：:]\s*', '', answer)
        
        labels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        # 丸数字からアルファベットへの変換マップ
        circled_to_alpha = {
            '①': 'A', '②': 'B', '③': 'C', '④': 'D', '⑤': 'E',
            '⑥': 'F', '⑦': 'G', '⑧': 'H', '⑨': 'I', '⑩': 'J',
            '⑪': 'K', '⑫': 'L', '⑬': 'M', '⑭': 'N', '⑮': 'O',
            '⑯': 'P', '⑰': 'Q', '⑱': 'R', '⑲': 'S', '⑳': 'T',
        }
        # 数字からアルファベットへの変換マップ
        num_to_alpha = {str(i): labels[i-1] for i in range(1, 27)}
        
        parts = []
        
        # 改行で分割してみる
        lines = answer.strip().split('\n')
        
        if len(lines) >= 2:
            # 複数行の場合：各行を解析
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 丸数字形式: ① 答え or ①. 答え
                match_circled = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])[.\s:：\t]*(.+)$', line)
                if match_circled:
                    label = circled_to_alpha.get(match_circled.group(1), 'A')
                    value = match_circled.group(2).strip()
                    parts.append(f'{label}. {value}')
                    continue
                
                # 数字形式: 1. 答え or 1) 答え
                match_num = re.match(r'^([0-9]+)[.\s:：\t\)）]*(.+)$', line)
                if match_num:
                    num = match_num.group(1)
                    label = num_to_alpha.get(num, labels[len(parts)] if len(parts) < len(labels) else 'A')
                    value = match_num.group(2).strip()
                    parts.append(f'{label}. {value}')
                    continue
                
                # A[TAB]答え or A. 答え or A: 答え or a. 答え 形式を解析
                match = re.match(r'^([A-Za-z])[.\s:：\t]+(.+)$', line)
                if match:
                    label = match.group(1).upper()
                    value = match.group(2).strip()
                    parts.append(f'{label}. {value}')
                else:
                    # ラベルなしの場合、順番に割り当て
                    if len(parts) < len(labels):
                        parts.append(f'{labels[len(parts)]}. {line}')
        else:
            # 1行の場合：様々な形式をチェック
            
            # まず丸数字形式を試す: ①xxx ②yyy or ① xxx ② yyy
            pattern_circled = r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])[.\s:：]*([^①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]+?)(?=\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|$)'
            matches_circled = re.findall(pattern_circled, answer)
            
            if matches_circled:
                for circled, value in matches_circled:
                    label = circled_to_alpha.get(circled, 'A')
                    parts.append(f'{label}. {value.strip().rstrip(",、")}')
            else:
                # A. xxx, B. yyy のようなカンマ区切りを試す（括弧内は除く）
                pattern = r'([A-Za-z])[.．:：\t]\s*(.+?)(?=\s*[,、]\s*[A-Za-z][.．:：\t]|$)'
                matches = re.findall(pattern, answer)
                
                if matches:
                    for label, value in matches:
                        parts.append(f'{label.upper()}. {value.strip().rstrip(",、")}')
                else:
                    # A. xxx B. yyy 形式（スペース区切り、ただし括弧内は保護）
                    # 括弧内を一時的に保護
                    protected = answer
                    bracket_contents = []
                    
                    def protect_brackets(m):
                        bracket_contents.append(m.group(0))
                        return f'__BRACKET_{len(bracket_contents)-1}__'
                    
                    protected = re.sub(r'\([^)]*\)', protect_brackets, protected)
                    protected = re.sub(r'（[^）]*）', protect_brackets, protected)
                    
                    # A. xxx B. yyy 形式を解析
                    pattern = r'([A-Za-z])[.．:：\t]\s*([^A-Za-z]+?)(?=\s*[A-Za-z][.．:：\t]|$)'
                    matches = re.findall(pattern, protected)
                    
                    if matches:
                        for label, value in matches:
                            # 括弧を復元
                            restored = value.strip()
                            for i, content in enumerate(bracket_contents):
                                restored = restored.replace(f'__BRACKET_{i}__', content)
                            parts.append(f'{label.upper()}. {restored}')
                    else:
                        # パターンに一致しない場合、そのまま返す
                        return f'正解：{answer}'
        
        if parts:
            return '正解：' + '　　'.join(parts)
        else:
            return f'正解：{answer}'

def format_question(question_text, answer_text):
    """問題文と正解を整形"""
    # 1. 空欄を統一マーカーに変換
    normalized = normalize_blanks(question_text)
    
    # 2. 空欄の数をカウント
    blank_count = normalized.count('{{BLANK}}')
    
    # 3. ですます調→である調に変換
    converted = convert_desu_masu(normalized)
    
    # 4. テキストをクリーンアップ
    cleaned = clean_text(converted)
    
    # 5. 空欄を適切な形式に変換
    formatted = format_blanks(cleaned, blank_count)
    
    # 6. 指示文を追加（空欄がある場合のみ）
    if blank_count > 0:
        instruction = '以下の記述の空欄に適切な語句を記入せよ。\n'
        formatted = instruction + formatted
    
    # 7. 正解を整形
    formatted_answer = format_answer(answer_text, blank_count)
    
    return {
        'question': formatted,
        'answer': formatted_answer,
        'blank_count': blank_count
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/format', methods=['POST'])
def format_api():
    data = request.get_json()
    question = data.get('question', '')
    answer = data.get('answer', '')
    
    result = format_question(question, answer)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
