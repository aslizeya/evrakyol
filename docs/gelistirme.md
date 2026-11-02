# Geliştirme notları

Kurulum, mimari ve test ayrıntıları. Projenin tanıtımı için: [README](../README.md)

## Depo yapısı

| Klasör         | İçerik                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `apps/web`     | Next.js web uygulaması (arayüz, API vekil uçları). Hesap ve kayıtlı işlem tabloları tanımlıdır; bu özellikler henüz yoktur |
| `services/api` | FastAPI servisi (sorularla ilerleyen rehber, veri toplama, indeksleme, RAG)                                                |
| `config`       | Ortak yapılandırma (işlem türleri, kaynak izin listesi, rehber içerikleri)                                                 |
| `eval`         | Değerlendirme seti ve raporları                                                                                            |
| `docs`         | Karar kaydı ve teknik notlar                                                                                               |

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

### Docker olmadan hızlı deneme

Veritabanı yerine kaynakları canlı çekip bellekte arayan yerel deneme kipi (yalnızca geliştirme içindir):

1. `.env.example` dosyasını `.env` olarak kopyalayın.
2. `.env` içinde `RETRIEVER_BACKEND=memory` yapın ve `INTERNAL_API_TOKEN` için uzun ve rastgele bir değer girin. Sorularla ilerleyen rehber yapay zekâ gerektirmez; serbest metin akışı (`/asistan`) için ayrıca `ANTHROPIC_API_KEY` gerekir.
3. Servisleri başlatın:

```bash
cd services/api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd apps/web && npm run dev
```

Web uygulaması kök klasördeki `.env` dosyasını `scripts/next-with-root-env.mjs` üzerinden okur.

## Veri toplama ve indeksleme

Kaynaklar ve izin verilen alan adları [config/sources.yaml](../config/sources.yaml) dosyasında tutulur. Hat şu adımlardan oluşur: izin listesi kontrolü → robots.txt → sunucu başına en az 3 saniye arayla çekme → başlık yapısı korunarak ayıklama (HTML/PDF, mevzuatta madde bazında) → parçalama → `bge-m3` ile embedding → `kb` şemasına yazma.

```bash
docker compose exec api python -m app.ingest sync     # yapılandırmadaki kaynakları veritabanına aktar
docker compose exec api python -m app.ingest run      # tüm aktif kaynakları çek ve indeksle
docker compose exec api python -m app.ingest status   # kaynakların son durumu
```

- `run` periyodik güncelleme için günlük zamanlanmış görev olarak çalıştırılır. İçeriği (özet hash'i) değişmeyen kaynaklar yeniden işlenmez; değişenler yeniden indekslenir ve değişiklik oranı `kb.ingestion_logs` tablosuna yazılır.
- Çekme başarısız olursa kaynağın mevcut parçaları silinmez.
- Giriş ekranı gösteren sayfalar (ör. e-Devlet hizmet sayfaları) ve çok kısa içerikler kaynak olarak kabul edilmez.
- Veritabanına yazmadan bir adresin nasıl ayıklanacağını görmek için: `python -m app.ingest preview <URL>`

## Sorularla ilerleyen rehber

Ana sayfadaki akış yapay zekâ kullanmaz. Kullanıcı işlemi seçer, ardından seçenekli soruları tek tek yanıtlar; cevaplara uyan adımlardan yol haritası oluşturulur. Serbest metin ve kişisel veri istenmez, cevaplar saklanmaz.

- **İçerik:** [config/rehber/](../config/rehber/) altında işlem başına bir YAML dosyası. Her adım ve uyarı, [config/sources.yaml](../config/sources.yaml) listesindeki bir kaynaktan birebir alıntıya dayanır; adımlar `goster_eger` koşullarıyla cevaplara bağlanır. Kaynakta karşılığı olmayan durumlar için bilgi yazılmaz, `notlar` ile kuruma yönlendirilir.
- **Doğrulama:** `python -m app.rehber kontrol` her alıntıyı kaynağın güncel metninde arar ve sonucu `config/rehber/dogrulama.json` dosyasına yazar. Çalışma anında yalnızca alıntıları doğrulanmış adımlar gösterilir; kaynak sayfası değişip alıntı kaybolursa ilgili adım kendiliğinden gizlenir ve komut hata koduyla çıkar.
- **Onay:** `onaylandi: false` olan içerikte kullanıcıya "henüz uzman onayından geçmemiştir" uyarısı gösterilir.
- **Uç nokta:** `POST /v1/rehber` durumsuzdur: o ana kadarki cevapları alır, sıradaki soruyu ya da yol haritasını döndürür.

## Yanıt üretimi (yapay zekâ, deneysel)

API iki uç nokta sunar (servis anahtarıyla, yalnızca web uygulaması çağırır):

- `POST /v1/understand`: metni MVP'deki işlemlerden birine sınıflandırır veya kapsam dışı olduğunu belirtir; eksik kritik bilgiler için en fazla 3 seçenekli soru döner.
- `POST /v1/roadmap`: hibrit aramayla ilgili kaynak parçalarını getirir, LLM'den şemaya uygun yol haritası ister ve her adımı kaynağa karşı doğrular.

Doğrulama kuralları: her adım ve uyarı, verilen bir kaynak parçasına kimlik ve birebir alıntıyla dayanmalıdır; dayanağı doğrulanamayan adım çıkarılır, kaynakta geçmeyen ücret gösterilmez, kaynak bağlantıları ve kontrol tarihleri veritabanından eklenir. Hiç doğrulanmış adım kalmazsa yol haritası yerine ilgili kuruma yönlendirme döner.

Veritabanı olmadan uçtan uca deneme (gerçek LLM çağrısı yapar, `ANTHROPIC_API_KEY` gerekir):

```bash
cd services/api && python -m app.rag demo "Babamdan kalan arabayı üzerime almak istiyorum"
```

## Web arayüzü

- **Akış:** Ana sayfada sorularla ilerleyen rehber yer alır (her ekranda tek soru, geri dönülebilir). Serbest metinle soru sorma deneysel olarak `/asistan` sayfasındadır: metin sınıflandırılır, gerekirse en fazla 3 seçenekli soru sorulur, ardından yol haritası gösterilir.
- **Yol haritası ekranı:** Numaralı adımlar, gerekli evraklar, kurum, ücret (yalnızca kaynakta varsa), kaynak bağlantıları ve son kontrol tarihleri, uyarılar, adım işaretleme ve ilerleme çubuğu bulunur.
- **PDF / yazdırma:** "Yazdır / PDF olarak kaydet" düğmesi tarayıcının yazdırma penceresini açar. Çıktıda yalnızca yol haritası ve kaynak adresleri yer alır.
- **Güvenlik:** Tarayıcı yapay zekâ servisine doğrudan bağlanmaz. `/api/rehber`, `/api/understand` ve `/api/roadmap` uçları girdiyi doğrular, IP başına hız sınırı uygular ve isteği servis anahtarıyla iletir.

## Testler

```bash
cd apps/web && npm run lint && npm run typecheck && npm test
```

```bash
cd apps/web && npx playwright install chromium && npm run test:e2e
```

Uçtan uca testler gerçek web sunucusunu sahte bir yapay zekâ servisiyle birlikte başlatır, akışı masaüstü ve mobil tarayıcıda sınar ve her aşamada axe-core ile WCAG A/AA denetimi yapar.

```bash
cd services/api && ruff check . && pytest
```

Veritabanı gerektiren API testleri yalnızca `DATABASE_URL` tanımlıysa çalışır.

## Sorumluluk reddi

Bilgiler resmi kaynaklardan derlenmiştir; işlem öncesinde ilgili kurumdan teyit ediniz. Hukuki tavsiye değildir.
