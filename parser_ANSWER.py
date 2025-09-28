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
    return s

def extract_answers_from_full_text(full_text):
    # захватываем всё после ANSWER: до следующего #N / TASK / QUESTION / двойного перевода строки / конца
    pattern = re.compile(
        r'(?i)ANSWER[:\s]\s*(.*?)(?=(?:\n\s*#\d+|\n\s*Task\b|\n\s*QUESTION:|\n{2,}|$))',
        flags=re.DOTALL
    )
    raw_matches = pattern.findall(full_text)

    answers = []
    seen = set()
    for raw in raw_matches:
        if not raw:
            continue
        # разделяем по строкам, берём первую непустую строку
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            candidate = raw.strip()
        else:
            candidate = lines[0]
            # если первая строка очень короткая (1-3 символа) и есть вторая - склеиваем 1 и 2
            if len(candidate) <= 3 and len(lines) >= 2:
                candidate = f"{lines[0]} {lines[1]}"
        candidate = clean_answer_text(candidate)

        # если кандидат очень длинный — оставляем только первое предложение
        if len(candidate) > 200:
            m = re.split(r'(?<=[\.\!\?])\s+', candidate, maxsplit=1)
            candidate = m[0].strip()

        # дополнительная фильтрация: если кандидат получился из одного слова по переносу (например "No" + "needed")
        # и следующий кусок в raw_matches может быть продолжением — но это сложный кейс.
        # Простая эвристика: если слово слишком короткое (<=2) и не акроним — пропускаем.
        if len(candidate) <= 2 and not re.match(r'^[A-Z0-9\{\}]+$', candidate):
            continue

        if candidate and candidate not in seen:
            seen.add(candidate)
            answers.append(candidate)

    # Ещё фактор: иногда в тексте есть явные одиночные ответы в формате "ANSWER: THM{...}" — если не найдены ответы,
    # попробуем найти такие случаи простой regex'ом
    if not answers:
        fallback = re.findall(r'(?i)ANSWER[:\s]\s*([A-Z0-9\{\}_\-]{3,})', full_text)
        for f in fallback:
            f = clean_answer_text(f)
            if f and f not in seen:
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
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
    except Exception as e:
        print("Ошибка парсера:", e)
    return []

if __name__ == "__main__":
    url = "https://medium.com/@Aircon/subdomain-enumeration-tryhackme-ad6ac4605a2d"
    answers = get_answers_from_medium(url, use_selenium=False, debug=True)
    if answers:
        print("Найденные ответы:")
        for i, a in enumerate(answers, 1):
            print(f"{i}. {a}")
    else:
        print("Ответов не найдено.")
