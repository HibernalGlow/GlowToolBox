def generate_opml():
    print("请输入标签名称(每行一个,输入空行结束):")
    names = set()  # 使用集合来去重
    
    while True:
        name = input().strip()
        if not name:  # 如果是空行就结束输入
            break
        names.add(name)
    
    # OPML 头部
    opml = '''<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>RSS Subscriptions</title>
    </head>
    <body>'''
    
    # 为每个名称生成一个 outline 元素
    for name in names:
        opml += f'''
        <outline text="{name}" title="{name}" type="rss" 
                xmlUrl="rsshub://wnacg/tag/{name}"/>'''
    
    # OPML 尾部
    opml += '''
    </body>
</opml>'''
    
    # 生成带时间戳的文件名
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'wnacg订阅_{timestamp}.opml'

    # 将生成的 OPML 保存到文件
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(opml)
    
    print(f"\n已生成 OPML 文件 '{filename}',共包含 {len(names)} 个订阅源")

if __name__ == "__main__":
    generate_opml()