import requests
from bs4 import BeautifulSoup
import re
import json

def extract_from_json_ld(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    for s in scripts:
        try:
            data = json.loads(s.string or '{}')
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                ab = it.get('articleBody') or it.get('description')
                if ab:
                    return ab
    return None

def clean_answer_text(s: str) -> str:
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^[\W_]+|[\W_]+$', '', s)
    # Удаляем лишние пробелы вокруг фигурных скобок или слешей, если это флаг/путь
    s = re.sub(r'\s*([/\{\}])', r'\1', s)
    s = re.sub(r'([/\{\}])\s*', r'\1', s)
    return s

def extract_answers_from_full_text(full_text):
    # Обновленный паттерн: захватывает Ans:, ANSWER:, Ans N: — case-insensitive, с номером или без
    pattern = re.compile(
        r'(?i)(?:ans|answer)[:\s]?\s*(?:#\d+:|\d+:)?\s*(.*?)(?=(?:\n\s*#\d+|\n\s*Task\b|\n\s*Ques\b|\n\s*Question\b|\n\s*(?:Ans|Answer)[:\s]|\n{2,}|$))',
        flags=re.DOTALL
    )
    raw_matches = pattern.findall(full_text)

    answers = []
    seen = set()
    for raw in raw_matches:
        if not raw:
            continue
        # Разделяем по строкам, берём первую непустую строку (или склеиваем короткие)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            candidate = raw.strip()
        else:
            candidate = lines[0]
            # Склеиваем короткую первую с второй, если нужно
            if len(candidate) <= 3 and len(lines) >= 2:
                candidate = f"{lines[0]} {lines[1]}"
            # Если всё ещё коротко, проверим третью
            if len(candidate) <= 5 and len(lines) >= 3:
                candidate = f"{candidate} {lines[2]}"
        candidate = clean_answer_text(candidate)

        # Ограничиваем длину: если >150 символов, берём до первого . ! ?
        if len(candidate) > 150:
            m = re.split(r'(?<=[\.\!\?])\s+', candidate, maxsplit=1)
            candidate = m[0].strip()

        # Фильтрация: пропускаем слишком короткие, кроме акронимов/флагов/путей
        if len(candidate) <= 2 and not re.match(r'^[A-Z0-9\{\}/\-_]+$', candidate):
            continue

        if candidate and candidate not in seen:
            seen.add(candidate)
            answers.append(candidate)

    # Fallback: простой regex для флагов/кодов вроде THM{} или путей, если основной паттерн ничего не поймал
    if not answers:
        fallback = re.findall(r'(?i)(?:ans|answer)[:\s]\s*([A-Za-z0-9/\{\}\-_]{3,})', full_text)
        for f in fallback:
            f = clean_answer_text(f)
            if f and f not in seen and len(f) > 2:
                answers.append(f)
                seen.add(f)

    return answers

def get_answers_from_medium(url, use_selenium=False, selenium_driver=None, debug=False):
    try:
        if use_selenium:
            if selenium_driver is None:
                raise ValueError("use_selenium=True требует selenium_driver (webdriver).")
            html = selenium_driver.page_source
        else:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
            }
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, 'html.parser')

        article = soup.find('article')
        if not article:
            for cls_re in ['meteredContent', 'postArticle-content', 'section-content', 'pw-post-body', 'n-content']:
                found = soup.find(attrs={'class': re.compile(cls_re)}) if cls_re else None
                if found:
                    article = found
                    break

        if article:
            full_text = article.get_text(separator='\n', strip=True)
        else:
            j = extract_from_json_ld(soup)
            if j:
                full_text = j
            else:
                body = soup.find('body')
                full_text = body.get_text(separator='\n', strip=True) if body else ''

        if debug:
            print("DEBUG: длина full_text:", len(full_text))
            print("DEBUG: первые 800 символов:\n", full_text[:800])

        answers = extract_answers_from_full_text(full_text)
        return answers

    except requests.exceptions.RequestException as e:
        print("Ошибка HTTP:", e)
        return []
    except Exception as e:
        print("Ошибка парсера:", e)
        return []

if __name__ == "__main__":
    url = "https://rahulk2903.medium.com/file-inclusion-tryhackme-walkthrough-99288e6dd348"
    answers = get_answers_from_medium(url, use_selenium=False, debug=True)
    if answers:
        print("Найденные ответы:")
        for i, a in enumerate(answers, 1):
            print(f"{i}. {a}")
    else:
        print("Ответов не найдено.")