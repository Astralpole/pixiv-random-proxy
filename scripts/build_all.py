import os, json, subprocess, sys, tempfile, shutil, time, random
from pathlib import Path

# 配置
TOKEN = os.environ['PIXIV_REFRESH_TOKEN']
COOKIE = os.environ['PIXIV_COOKIE']
USER_ID = os.environ['PIXIV_USER_ID']

# 创建配置
config_dir = Path.home() / '.config' / 'gallery-dl'
config_dir.mkdir(parents=True, exist_ok=True)
config = {
    "extractor": {
        "pixiv": {
            "refresh-token": TOKEN,
            "cookies": {"PHPSESSID": COOKIE}
        }
    }
}
with open(config_dir / 'config.json', 'w') as f:
    json.dump(config, f)

# 获取关注列表
print("Fetching following artists...")
result = subprocess.run(
    ['gallery-dl', '--get-urls', f'https://www.pixiv.net/users/{USER_ID}/following'],
    capture_output=True, text=True
)
artist_ids = set()
for line in result.stdout.splitlines():
    if '/users/' in line:
        aid = line.split('/users/')[1].split('/')[0].split('?')[0]
        if aid.isdigit():
            artist_ids.add(aid)
artist_ids = sorted(artist_ids)
with open('artists_index.txt', 'w') as f:
    f.write('\n'.join(artist_ids))

# 创建输出目录
os.makedirs('data/artists', exist_ok=True)
os.makedirs('data/pid', exist_ok=True)
os.makedirs('data/pid_date_map', exist_ok=True)

# 爬取每个画师的作品和日期映射
all_date_map = {}
for aid in artist_ids:
    print(f">> Processing artist {aid}")
    tmpdir = tempfile.mkdtemp()
    # 获取作品列表
    res = subprocess.run(
        ['gallery-dl', '--get-urls', '--no-download', '--write-info-json', '-d', tmpdir,
         f'https://www.pixiv.net/users/{aid}/illustrations'],
        capture_output=True, text=True
    )
    # 提取 PID_pX 写入 artists 文件
    pids = set()
    for line in res.stdout.splitlines():
        if '/illustrations/' in line:
            parts = line.split('/')
            if len(parts) >= 3:
                pid_part = parts[-1]
                if '_p' in pid_part:
                    pids.add(pid_part)
    if pids:
        with open(f'data/artists/{aid}.json', 'w') as f:
            f.write('\n'.join(sorted(pids)))
    else:
        # 无作品也写空文件
        open(f'data/artists/{aid}.json', 'w').close()

    # 处理 info.json 提取 date_url
    pid_date = {}
    for root, dirs, files in os.walk(tmpdir):
        for file in files:
            if file.endswith('.json'):
                try:
                    with open(os.path.join(root, file)) as f:
                        data = json.load(f)
                    pid = str(data.get('illust_id', ''))
                    date_url = data.get('date_url', '')
                    if pid and date_url:
                        pid_date[pid] = date_url
                except:
                    pass
    if pid_date:
        with open(f'data/pid_date_map/{aid}.json', 'w') as f:
            json.dump(pid_date, f)
        all_date_map.update(pid_date)

    # 构建反向索引
    if pids:
        from collections import defaultdict
        pid_pages = defaultdict(list)
        for pp in pids:
            if '_' in pp:
                pid, page = pp.split('_', 1)
                pid_pages[pid].append(page)
        for pid, pages in pid_pages.items():
            with open(f'data/pid/{pid}.json', 'w') as f:
                json.dump(sorted(pages), f)

    # 清理临时目录
    shutil.rmtree(tmpdir)
    # 随机休眠，避免 429
    time.sleep(random.randint(6, 9))

# 写入全局日期映射
with open('data/all_pids_map.json', 'w') as f:
    json.dump(all_date_map, f)

# 生成 pid 索引
pid_list = sorted(os.listdir('data/pid'))
with open('data/pid_index.txt', 'w') as f:
    for pid_file in pid_list:
        if pid_file.endswith('.json'):
            f.write(pid_file[:-5] + '\n')

print("Done.")