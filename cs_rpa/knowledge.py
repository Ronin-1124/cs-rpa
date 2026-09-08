"""CSV source preservation, repeatable import and lightweight Chinese retrieval."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time


def terms(text):
    text = text.lower()
    words = re.findall(r'[a-z0-9][a-z0-9_.+-]*', text)
    for segment in re.findall(r'[\u4e00-\u9fff]+', text):
        words.extend(segment[i:i+2] for i in range(len(segment)-1))
    return set(words)


class Knowledge:
    def __init__(self, db):
        self.db = db

    def import_csv(self, filename, text):
        if not filename.lower().endswith('.csv') or len(text) > 4_000_000:
            raise ValueError('请选择 4 MB 以内的 CSV 文件')
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        columns = reader.fieldnames or []
        question = next((c for c in columns if c == '问题'), None)
        answer = next((c for c in columns if c == '答案' or '话术内容' in c or '快捷短语内容' in c), None)
        title = next((c for c in columns if '话术标题' in c), None)
        product_column = next((c for c in columns if c == '产品型号'), None)
        if not answer:
            raise ValueError('未找到“答案”“话术内容”或“快捷短语内容”列')
        inserted, duplicate, empty = 0, 0, 0
        for row_number, row in enumerate(reader, 2):
            content = (row.get(answer) or '').strip()
            if not content:
                empty += 1
                continue
            label = (row.get(question or title) or content[:60]).strip()
            product = (row.get(product_column) or '').strip()
            digest = hashlib.sha256(json.dumps([product, label, content], ensure_ascii=False).encode()).hexdigest()
            source = {'file': filename, 'row': row_number}
            existing = self.db.one('SELECT sources FROM knowledge WHERE id=?', (digest,))
            if existing:
                sources = json.loads(existing['sources'])
                if source not in sources:
                    sources.append(source)
                    self.db.execute('UPDATE knowledge SET sources=? WHERE id=?', (json.dumps(sources, ensure_ascii=False), digest))
                duplicate += 1
            else:
                self.db.execute('INSERT INTO knowledge VALUES(?,?,?,?,?,1,?)', (digest, label, content, product, json.dumps([source], ensure_ascii=False), time.time()))
                inserted += 1
        return {'file': filename, 'inserted': inserted, 'duplicates': duplicate, 'empty': empty}

    def search(self, query, limit=6):
        query_terms = terms(query)
        if not query_terms:
            return []
        candidates = []
        for row in self.db.rows('SELECT * FROM knowledge WHERE enabled=1'):
            title_terms = terms(row['title'] + ' ' + row['product'])
            body_terms = terms(row['content'])
            overlap = query_terms & (title_terms | body_terms)
            if not overlap:
                continue
            score = len(overlap & title_terms) * 3 + len(overlap)
            product_tokens = re.findall(r'[a-z]+[ -]?\d[a-z0-9]*', row['product'].lower())
            requested = re.findall(r'[a-z]+[ -]?\d[a-z0-9]*', query.lower())
            if requested and product_tokens and not set(requested) & set(product_tokens):
                continue
            if len(overlap) < 2 and not any(re.search(r'\d', t) for t in overlap):
                continue
            candidates.append((score, row))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [{'id': r['id'], 'title': r['title'], 'content': r['content'][:3000],
                 'product': r['product'], 'sources': json.loads(r['sources'])} for _, r in candidates[:limit]]
