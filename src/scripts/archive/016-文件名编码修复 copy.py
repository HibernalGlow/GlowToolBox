def analyze_and_fix_encoding(wrong_text):
    """
    分析并尝试修复乱码文本
    返回: (修复后的文本, 使用的编码方法, 详细信息)
    """
    print(f"原始文本: {wrong_text}")
    
    # 1. 分析原始文本
    print("\n1. Unicode 分析:")
    for char in wrong_text:
        print(f"{char}: U+{ord(char):04X}")
    
    # 2. 尝试不同的编码转换路径
    encoding_paths = [
        # (中间编码, 目标编码, 描述)
        ('cp932', 'cp437', 'CP932 -> CP437'),
        ('cp437', 'cp932', 'CP437 -> CP932'),
        ('latin1', 'cp932', 'Latin1 -> CP932'),
        ('cp932', 'latin1', 'CP932 -> Latin1'),
        ('shift_jis', 'cp437', 'Shift_JIS -> CP437'),
        ('cp437', 'shift_jis', 'CP437 -> Shift_JIS'),
        ('shift_jis', 'latin1', 'Shift_JIS -> Latin1'),
        ('latin1', 'shift_jis', 'Latin1 -> Shift_JIS'),
        ('gbk', 'cp932', 'GBK -> CP932'),
        ('cp932', 'gbk', 'CP932 -> GBK'),
        ('utf-8', 'cp932', 'UTF-8 -> CP932'),
        ('cp932', 'utf-8', 'CP932 -> UTF-8'),
        ('big5', 'cp932', 'Big5 -> CP932'),
        ('cp932', 'big5', 'CP932 -> Big5'),
        ('euc_jp', 'cp932', 'EUC_JP -> CP932'),
        ('cp932', 'euc_jp', 'CP932 -> EUC_JP'),
        ('euc_jp', 'cp437', 'EUC_JP -> CP437'),
        ('cp437', 'euc_jp', 'CP437 -> EUC_JP'),
        ('iso2022_jp', 'cp932', 'ISO2022_JP -> CP932'),
        ('cp932', 'iso2022_jp', 'CP932 -> ISO2022_JP'),
        # 多步转换
        ('latin1', 'cp437', 'cp932', 'Latin1 -> CP437 -> CP932'),
        ('cp932', 'cp437', 'latin1', 'CP932 -> CP437 -> Latin1'),
        ('shift_jis', 'cp437', 'cp932', 'Shift_JIS -> CP437 -> CP932'),
        ('latin1', 'shift_jis', 'cp932', 'Latin1 -> Shift_JIS -> CP932'),
    ]
    
    results = []
    print("\n2. 编码转换尝试:")
    
    for *encodings, desc in encoding_paths:
        try:
            # 处理多步转换
            text = wrong_text
            bytes_sequence = []
            
            # 如果是多步转换
            for i in range(len(encodings)-1):
                # 编码
                mid_bytes = text.encode(encodings[i], errors='ignore')
                bytes_sequence.append(mid_bytes.hex())
                # 解码
                text = mid_bytes.decode(encodings[i+1], errors='ignore')
            
            # 检查结果是否包含有效的字符
            has_valid = any(
                '\u4e00' <= c <= '\u9fff' or  # 中文
                '\u3040' <= c <= '\u30ff' or  # 日文平假名片假名
                '\u31f0' <= c <= '\u31ff' or  # 日文片假名扩展
                '\u3000' <= c <= '\u303f' or  # 日文标点
                ('A' <= c <= 'Z' and len(text) > 3)  # 英文（避免误判）
                for c in text
            )
            
            results.append({
                'text': text,
                'method': desc,
                'bytes': ' -> '.join(bytes_sequence),
                'valid': has_valid
            })
            
            print(f"\n{desc}:")
            print(f"字节序列: {' -> '.join(bytes_sequence)}")
            print(f"转换结果: {text}")
            print(f"包含有效字符: {'是' if has_valid else '否'}")
            
        except Exception as e:
            print(f"\n{desc} 失败: {e}")
    
    # 3. 选择最佳结果
    valid_results = [r for r in results if r['valid']]
    if valid_results:
        # 优先选择包含 "PSD" 的结果
        psd_results = [r for r in valid_results if "PSD" in r['text']]
        # 其次选择包含日文字符的结果
        jp_results = [r for r in valid_results if any('\u3040' <= c <= '\u30ff' for c in r['text'])]
        
        if psd_results:
            best_result = psd_results[0]
        elif jp_results:
            best_result = jp_results[0]
        else:
            best_result = valid_results[0]
            
        print(f"\n最佳修复结果: {best_result['text']}")
        print(f"使用方法: {best_result['method']}")
        return best_result['text'], best_result['method'], results
    else:
        print("\n没有找到有效的修复结果")
        return wrong_text, None, results

def test_encoding():
    """
    测试不同的乱码情况
    """
    test_cases = [
        "偊偭偪嬁",  # 示例1
        "PSDííÑ∩Ñ≤Ñ╔Ñφ",  # 示例2
        "PSDﾃ篠ｽﾃ｣窶榲ｽﾅ",  # 示例3
        "縺ｧ縺吶°縺ｭ｡ｼ",  # 示例4
        # 可以添加更多测试用例
    ]
    
    print("=== 编码修复测试 ===")
    for i, text in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print("="*50)
        fixed_text, method, _ = analyze_and_fix_encoding(text)
        print("="*50)

if __name__ == "__main__":
    test_encoding()