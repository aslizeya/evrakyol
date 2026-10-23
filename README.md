# Evrakyol

Resmi işlemler için yalnızca resmi kaynaklara dayanan, her adımın kaynağını gösteren kişiselleştirilmiş yol haritası.

> Proje geliştirme aşamasındadır. Tam README (problem, vizyon, ürün kararları, mimari, değerlendirme sonuçları) yayın aşamasında eklenecektir. Kararlar için: [docs/kararlar.md](docs/kararlar.md)

**Proje sahibi:** Aslı Zeynep Aydemir — [GitHub](https://github.com/aslizeya)

## Depo yapısı

| Klasör          | İçerik                                                             |
| --------------- | ------------------------------------------------------------------ |
| `apps/web`      | Next.js web uygulaması (arayüz, kimlik doğrulama, kayıtlı işlemler) |
| `services/api`  | FastAPI yapay zekâ servisi (veri toplama, indeksleme, RAG)          |
| `config`        | Ortak yapılandırma (işlem türleri, kaynak izin listesi)            |
| `eval`          | Değerlendirme seti ve raporları                                     |
| `docs`          | Karar kaydı ve teknik notlar                                       |

## Yerel kurulum

Gereksinimler: Docker Desktop, Node.js 24+, Python 3.13+

```bash
cp .env.example .env
docker compose up -d
```

Bu komut Postgres (pgvector), Redis ve API servisini başlatır; API açılışta `kb` şemasının migration'larını uygular. API: http://localhost:8000/health

Web uygulaması:

```bash
cd apps/web
npm install
npm run db:migrate
npm run db:seed
npm run dev
```

Web: http://localhost:3000

## Testler

```bash
cd apps/web && npm run lint && npm run typecheck && npm test
```

```bash
cd services/api && ruff check . && pytest
```

Veritabanı gerektiren API testleri yalnızca `DATABASE_URL` tanımlıysa çalışır.

## Sorumluluk reddi

Bilgiler resmi kaynaklardan derlenmiştir; işlem öncesinde ilgili kurumdan teyit ediniz. Hukuki tavsiye değildir.
