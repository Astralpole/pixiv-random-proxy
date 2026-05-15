import os, json, requests, time, sys, random, subprocess, tempfile, shutil
from pathlib import Path
from collections import defaultdict

TOKEN = os.environ['PIXIV_REFRESH_TOKEN']
COOKIE = os.environ['PIXIV_COOKIE']
USER_ID = os.environ['PIXIV_USER_ID']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Cookie': f'PHPSESSID={COOKIE}',
    'Referer': 'https://www.pixiv.net/',
}

def api_get(url, params=None):
    for retry in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"  API {resp.status_code}, retry {retry+1}...")
                time.sleep(5)
        except Exception as e:
            print(f"  Request error: {e}, retry {retry+1}...")
            time.sleep(5)
    return None

# ---------- 获取关注列表 ----------
print("Fetching following artists...")
artist_ids = []
offset = 0
limit = 100
while True:
    data = api_get(f'https://www.pixiv.net/ajax/user/{USER_ID}/following', 
                   params={'offset': offset, 'limit': limit, 'rest': 'show'})
    if not data or 'body' not in data:
        print("Failed to fetch following list. Exiting.")
        sys.exit(1)
    artists = data['body'].get('users', [])
    if not artists:
        break
    artist_ids.extend(str(a['userId']) for a in artists)
    offset += limit
    time.sleep(1)

artist_ids = sorted(set(artist_ids))
print(f"Found {len(artist_ids)} artists")
with open('artists_index.txt', 'w') as f:
    f.write('\n'.join(artist_ids))

# ---------- 遍历画师 ----------
os.makedirs('data/artists', exist_ok=True)
os.makedirs('data/pid', exist_ok=True)

total = len(artist_ids)
total_works = 0
error_list = []

for idx, aid in enumerate(artist_ids, 1):
    print(f"[{idx}/{total}] Processing artist {aid} ...", end=' ', flush=True)
    works_written = False

    # ----- 主路径：Pixiv Ajax API -----
    profile = api_get(f'https://www.pixiv.net/ajax/user/{aid}/profile/all')
    if profile and 'body' in profile:
        pids = set()
        for key in ('illusts', 'manga'):
            items = profile['body'].get(key)
            if not items:
                continue
            # 兼容字典或列表
            if isinstance(items, dict):
                pids.update(items.keys())
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        pid = str(item.get('id', ''))
                        if pid:
                            pids.add(pid)
                    elif isinstance(item, str):
                        pids.add(item)
        if pids:
            with open(f'data/artists/{aid}.json', 'w') as f:
                f.write('\n'.join(sorted(str(p) for p in pids)))
            total_works += len(pids)
            print(f"OK ({len(pids)} works) [API]")
            works_written = True

    if not works_written:
        # ----- 降级路径：gallery-dl -----
        print("API failed, fallback to gallery-dl...", end=' ')
        tmpdir = tempfile.mkdtemp()
        try:
            subprocess.run(
                ['gallery-dl', '--write-info-json', '--no-download', '-d', tmpdir,
                 f'https://www.pixiv.net/users/{aid}/illustrations'],
                capture_output=True, text=True, timeout=120
            )

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
                            # R-18 过滤
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
                for pp in pids_set:
                    if '_' in pp:
                        pid, page = pp.split('_', 1)
                        pid_pages[pid].append(page)
                for pid, pages in pid_pages.items():
                    with open(f'data/pid/{pid}.json', 'w') as f:
                        json.dump(sorted(pages), f)

                total_works += len(pids_set)
                print(f"OK ({len(pids_set)} works) [gallery-dl]")
            else:
                print("OK (0 works) [gallery-dl]")
                open(f'data/artists/{aid}.json', 'w').close()
        except subprocess.TimeoutExpired:
            print("TIMEOUT (gallery-dl)")
            error_list.append(aid)
            open(f'data/artists/{aid}.json', 'w').close()
        except Exception as e:
            print(f"ERROR: {e}")
            error_list.append(aid)
            open(f'data/artists/{aid}.json', 'w').close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    time.sleep(random.randint(5, 8))

# ---------- 生成 pid 索引 ----------
pid_files = sorted(os.listdir('data/pid'))
with open('data/pid_index.txt', 'w') as f:
    for pf in pid_files:
        if pf.endswith('.json'):
            f.write(pf[:-5] + '\n')

print(f"\n{'='*50}")
print(f"Done! Total artists: {total}")
print(f"Total works (all): {total_works}")
if error_list:
    print(f"Errors on ({len(error_list)}): {', '.join(error_list[:10])}...")
print(f"{'='*50}")