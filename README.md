# Evrakyol

Resmi işlemler için yalnızca resmi kaynaklara dayanan, her adımın kaynağını gösteren kişiselleştirilmiş yol haritası.

> Proje geliştirme aşamasındadır. Tam README (problem, vizyon, ürün kararları, mimari, değerlendirme sonuçları) yayın aşamasında eklenecektir. Kararlar için: [docs/kararlar.md](docs/kararlar.md)

**Proje sahibi:** Aslı Zeynep Aydemir — [GitHub](https://github.com/aslizeya)

## Depo yapısı

| Klasör         | İçerik                                                              |
| -------------- | ------------------------------------------------------------------- |
| `apps/web`     | Next.js web uygulaması (arayüz, kimlik doğrulama, kayıtlı işlemler) |
| `services/api` | FastAPI yapay zekâ servisi (veri toplama, indeksleme, RAG)          |
| `config`       | Ortak yapılandırma (işlem türleri, kaynak izin listesi)             |
| `eval`         | Değerlendirme seti ve raporları                                     |
| `docs`         | Karar kaydı ve teknik notlar                                        |

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

## Veri toplama ve indeksleme

Kaynaklar ve izin verilen alan adları [config/sources.yaml](config/sources.yaml) dosyasında tutulur. Hat şu adımlardan oluşur: izin listesi kontrolü → robots.txt → sunucu başına en az 3 saniye arayla çekme → başlık yapısı korunarak ayıklama (HTML/PDF, mevzuatta madde bazında) → parçalama → `bge-m3` ile embedding → `kb` şemasına yazma.

```bash
docker compose exec api python -m app.ingest sync     # yapılandırmadaki kaynakları veritabanına aktar
docker compose exec api python -m app.ingest run      # tüm aktif kaynakları çek ve indeksle
docker compose exec api python -m app.ingest status   # kaynakların son durumu
```

- `run` periyodik güncelleme için günlük zamanlanmış görev olarak çalıştırılır. İçeriği (özet hash'i) değişmeyen kaynaklar yeniden işlenmez; değişenler yeniden indekslenir ve değişiklik oranı `kb.ingestion_logs` tablosuna yazılır.
- Çekme başarısız olursa kaynağın mevcut parçaları silinmez.
- Giriş ekranı gösteren sayfalar (ör. e-Devlet hizmet sayfaları) ve çok kısa içerikler kaynak olarak kabul edilmez.
- Veritabanına yazmadan bir adresin nasıl ayıklanacağını görmek için: `python -m app.ingest preview <URL>`

## Yanıt üretimi

API iki uç nokta sunar (servis anahtarıyla, yalnızca web uygulaması çağırır):

- `POST /v1/understand`: metni MVP'deki işlemlerden birine sınıflandırır veya kapsam dışı olduğunu belirtir; eksik kritik bilgiler için en fazla 3 seçenekli soru döner.
- `POST /v1/roadmap`: hibrit aramayla ilgili kaynak parçalarını getirir, LLM'den şemaya uygun yol haritası ister ve her adımı kaynağa karşı doğrular.

Doğrulama kuralları: her adım ve uyarı, verilen bir kaynak parçasına kimlik ve birebir alıntıyla dayanmalıdır; dayanağı doğrulanamayan adım çıkarılır, kaynakta geçmeyen ücret gösterilmez, kaynak bağlantıları ve kontrol tarihleri veritabanından eklenir. Hiç doğrulanmış adım kalmazsa yol haritası yerine ilgili kuruma yönlendirme döner.

Veritabanı olmadan uçtan uca deneme (gerçek LLM çağrısı yapar, `ANTHROPIC_API_KEY` gerekir):

```bash
cd services/api && python -m app.rag demo "Babamdan kalan arabayı üzerime almak istiyorum"
```

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
