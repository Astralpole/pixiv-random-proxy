import sys, json
from collections import defaultdict

input_file = sys.argv[1]
output_dir = sys.argv[2]

pid_pages = defaultdict(list)
with open(input_file) as f:
    for line in f:
        line = line.strip()
        if '_' not in line:
            continue
        pid, page = line.split('_', 1)
        pid_pages[pid].append(page)

for pid, pages in pid_pages.items():
    with open(f'{output_dir}/{pid}.json', 'w') as fout:
        json.dump(sorted(pages), fout)