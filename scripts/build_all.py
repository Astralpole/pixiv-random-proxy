import os, json, subprocess, sys, tempfile, shutil, time, random
from pathlib import Path
from collections import defaultdict

TOKEN = os.environ['PIXIV_REFRESH_TOKEN']
COOKIE = os.environ['PIXIV_COOKIE']
USER_ID = os.environ['PIXIV_USER_ID']

# 创建 gallery-dl 配置
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
    capture_output=True, text=True, timeout=60
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
print(f"Found {len(artist_ids)} artists")

os.makedirs('data/artists', exist_ok=True)
os.makedirs('data/pid', exist_ok=True)

total = len(artist_ids)
total_works = 0
timeout_artists = []
error_artists = []

for idx, aid in enumerate(artist_ids, 1):
    print(f"[{idx}/{total}] Processing artist {aid} ...", end=' ', flush=True)
    tmpdir = tempfile.mkdtemp()
    
    try:
        # 只用 --write-info-json，不再用 --get-urls
        proc = subprocess.run(
            ['gallery-dl', '--write-info-json', '--no-download', '-d', tmpdir,
             f'https://www.pixiv.net/users/{aid}/illustrations'],
            capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT - skipped")
        timeout_artists.append(aid)
        shutil.rmtree(tmpdir, ignore_errors=True)
        continue
    except Exception as e:
        print(f"ERROR: {e}")
        error_artists.append(aid)
        shutil.rmtree(tmpdir, ignore_errors=True)
        continue

    pids_set = set()
    pid_pages = defaultdict(list)

    for root, dirs, files in os.walk(tmpdir):
        for file in files:
            if file.endswith('.json'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    pid = str(data.get('illust_id', ''))
                    if not pid:
                        continue
                    # 过滤 R-18
                    tags = []
                    if 'tags' in data:
                        tags_data = data['tags']
                        if isinstance(tags_data, dict) and 'tags' in tags_data:
                            tags = [t.get('tag', '') for t in tags_data['tags']]
                        elif isinstance(tags_data, list):
                            tags = [t.get('tag', '') if isinstance(t, dict) else str(t) for t in tags_data]
                    if 'R-18' in tags or 'R-18G' in tags:
                        continue
                    page_count = data.get('page_count', 1)
                    for p in range(page_count):
                        pids_set.add(f"{pid}_p{p}")
                except:
                    pass

    if pids_set:
        with open(f'data/artists/{aid}.json', 'w') as f:
            f.write('\n'.join(sorted(pids_set)))
    else:
        open(f'data/artists/{aid}.json', 'w').close()

    # 构建反向索引
    for pp in pids_set:
        if '_' in pp:
            pid, page = pp.split('_', 1)
            pid_pages[pid].append(page)
    for pid, pages in pid_pages.items():
        with open(f'data/pid/{pid}.json', 'w') as f:
            json.dump(sorted(pages), f)

    shutil.rmtree(tmpdir, ignore_errors=True)
    total_works += len(pids_set)
    print(f"OK ({len(pids_set)} works)")
    time.sleep(random.randint(5, 8))

# 生成 pid 索引
pid_files = sorted(os.listdir('data/pid'))
with open('data/pid_index.txt', 'w') as f:
    for pf in pid_files:
        if pf.endswith('.json'):
            f.write(pf[:-5] + '\n')

print(f"\n{'='*50}")
print(f"Done! Total artists: {total}")
print(f"Total works (non R-18): {total_works}")
if timeout_artists:
    print(f"Timeout artists ({len(timeout_artists)}): {', '.join(timeout_artists[:10])}...")
if error_artists:
    print(f"Error artists ({len(error_artists)}): {', '.join(error_artists[:10])}...")
print(f"{'='*50}")