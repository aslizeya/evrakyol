# Karar Kaydı

Ürün kararları proje sahibi Aslı Zeynep Aydemir tarafından verilir. Teknik varsayılanlar bu dosyada gerekçeleriyle not edilir.

## Ürün kararları

| Tarih      | Karar                                                                      | Gerekçe                                                                                        |
| ---------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 2026-10-23 | Proje adı **Evrakyol**                                                     | Kısa, Türkçe ve ürünün işlevini anlatıyor.                                                     |
| 2026-10-23 | Türkiye Noterler Birliği (tnb.org.tr) izin listesine dahil                 | Araç devri ve mirasçılık belgesi noterde yapılıyor; alan adı `.gov.tr` olmasa da resmi kaynak. |
| 2026-10-23 | Embedding modeli kendi sunucumuzda çalışır (`BAAI/bge-m3`)                 | Ücretsiz, Türkçe'de güçlü; kullanıcı metni embedding için üçüncü tarafa gönderilmez.           |
| 2026-10-23 | Değerlendirme setinin beklenen cevaplarını proje sahibi onaylar            | Yapay zekânın kendi ürettiği cevapla ölçülmesi döngüsel ve yanıltıcı olur.                     |
| 2026-10-23 | Web (Next.js) + yapay zekâ servisi (FastAPI) iki ayrı parça                | Veri toplama, embedding ve değerlendirme araçları Python ekosisteminde daha olgun.             |
| 2026-10-23 | Netleştirici sorular işlem türüne özgü, önceden tanımlı alanlardan seçilir | Tutarlı sorular, kişisel veri istenmemesi, aynı durum için önbelleğe alınabilir yanıt.         |

## Teknik varsayılanlar

| Tarih      | Karar                                                                                   | Gerekçe                                                                                              |
| ---------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 2026-10-23 | Postgres iki şemaya ayrıldı: `app` (Prisma) ve `kb` (Alembic)                           | İki ORM'in aynı tabloları değiştirip birbirinin migration'larını bozmasını önler.                    |
| 2026-10-23 | İşlem türleri `config/process_types.json` dosyasında tek kaynaktan                      | Web seed'i ve API sınıflandırıcısı aynı listeyi kullanır; listeler birbirinden kopamaz.              |
| 2026-10-23 | Tek `.env` dosyası kök klasörde                                                         | Web, API ve Docker Compose aynı ayarları okur. API, `postgresql://` adresine sürücüyü kendisi ekler. |
| 2026-10-23 | Anahtar kelime araması Postgres `turkish` tam metin yapılandırmasıyla (üretilmiş sütun) | Ek bir arama servisi gerektirmez; vektör aramasıyla aynı sorguda birleştirilebilir (hibrit arama).   |
| 2026-10-23 | Vektör indeksi HNSW + kosinüs uzaklığı                                                  | Küçük-orta veri boyutunda yüksek isabet, ek ayar gerektirmez.                                        |
| 2026-10-23 | Varsayılan LLM: Anthropic Claude (`LLM_PROVIDER`, `LLM_MODEL` ile değiştirilebilir)     | Proje sahibi sağlayıcı belirtmedi; katman sağlayıcıdan bağımsız tasarlanacak (3. aşama).             |
| 2026-10-23 | Barındırma: Neon (Postgres + pgvector), Railway (API), Vercel (web)                     | Neon pgvector'ü hazır sunar; Railway Dockerfile ile çalışır.                                         |
| 2026-10-23 | Node 24, Next.js 16, Prisma 7 (driver adapter), Python 3.13, SQLAlchemy 2.1             | Geliştirme başladığında güncel kararlı sürümler.                                                     |

## Veri toplama (2. aşama)

| Tarih      | Karar                                                                              | Gerekçe                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-10-24 | İlk iki işlem: miras yoluyla araç devri ve mirasçılık belgesi                      | Kaynakları büyük ölçüde ortak (noter, vergi dairesi, trafik tescil).                                                                            |
| 2026-10-24 | e-Devlet hizmet sayfaları kaynak olarak kullanılmıyor                              | Giriş yapılmadan yalnızca "kimliğinizi doğrulayın" ekranı görünüyor; bilgi içermiyor. Hat bu ekranları otomatik reddeder.                       |
| 2026-10-24 | HTML ayıklayıcı projeye özel yazıldı (hazır kütüphane yerine)                      | EGM ve TNB sayfalarında başlıklar `<h2>` değil kalın/büyük harfli satır; hazır kütüphane bunları atıyor ve evrak listesi bağlamından kopuyordu. |
| 2026-10-24 | robots.txt'ye ulaşılamazsa site taranmaz; robots.txt yoksa kısıtlama yok sayılır   | RFC 9309'a uygun, temkinli davranış.                                                                                                            |
| 2026-10-24 | Yönlendirmeler her adımda izin listesine göre denetlenir                           | Resmi bir adres, izin listesi dışındaki bir siteye yönlendirse bile o siteye istek atılmaz.                                                     |
| 2026-10-24 | trafik.gov.tr `/kurumlar/` altındaki PDF'ler (ör. 2026 ceza rehberi) kullanılmıyor | Sitenin robots.txt dosyası bu klasörü yasaklıyor.                                                                                               |
| 2026-10-24 | GİB'in vergi konuları sayfası yerine resmi broşür PDF'i kullanılıyor               | Sayfa içeriği tarayıcıda JavaScript ile yükleniyor; broşür aynı bilgiyi içeriyor ve tarihli (Eylül 2026).                                       |
| 2026-10-24 | Büyük kanunlardan yalnızca ilgili maddeler alınıyor (ör. TMK 495–501, 598)         | Kanunun tamamı ilgisiz yüzlerce parça üretir ve aramayı zayıflatır. Maddeler `config/sources.yaml` içinden değiştirilebilir.                    |

## Yanıt üretimi (3. aşama)

| Tarih      | Karar                                                                                                                 | Gerekçe                                                                                                                                 |
| ---------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-10-24 | Varsayılan model `claude-opus-5-5`, effort `high`; `LLM_MODEL=claude-sonnet-5-5` ile daha ucuz seçenek                | Hukuki/idari doğruluk maliyetten önce gelir. Değerlendirme (4. aşama) sonuçlarına göre yeniden bakılacak.                               |
| 2026-10-24 | Sunucu tarafı yedek model (`fallbacks: "default"`) açık                                                               | Güvenlik sınıflandırıcısının yanlışlıkla reddettiği istekler kullanıcıya hata olarak dönmesin. `LLM_FALLBACKS=false` ile kapatılabilir. |
| 2026-10-24 | LLM çıktısı JSON şemasıyla kısıtlanıyor (structured outputs)                                                          | Serbest metin yerine doğrulanabilir alanlar.                                                                                            |
| 2026-10-24 | Her adım ve uyarı için kaynak kimliği + birebir alıntı zorunlu; sunucu alıntıyı kaynakta arar                         | "Kaynak gösterildi" ile "kaynağa dayanıyor" aynı şey değil. Doğrulanamayan adım/uyarı gösterilmez.                                      |
| 2026-10-24 | Kaynak başlığı, adresi, kontrol tarihi veritabanından ekleniyor                                                       | LLM'in adres uydurma ihtimali tamamen ortadan kalkar.                                                                                   |
| 2026-10-24 | Ücret, ancak içindeki her sayı dayanak kaynakta geçiyorsa gösteriliyor                                                | Ücretler en sık değişen ve en riskli bilgi.                                                                                             |
| 2026-10-24 | Şemaya uymayan yanıt bir kez yeniden deneniyor; ikinci hatada kullanıcıya hata                                        | Proje belgesindeki "uydurma" yasağı.                                                                                                    |
| 2026-10-24 | Hibrit arama: vektör + Türkçe tam metin (VEYA araması), Reciprocal Rank Fusion                                        | Doğal dildeki uzun sorular VE aramasıyla sonuç bulamıyor; iki yöntemin sıralamaları birleştirilince ikisinin de güçlü yanı kalıyor.     |
| 2026-10-24 | Kişisel veriler (T.C. kimlik, plaka, telefon, e-posta, IBAN, adres) LLM'e gitmeden ve kaydedilmeden önce maskeleniyor | KVKK; yurt dışına veri aktarımı riskini azaltır. Maskelenmiş metin web'e döner, kaydedilen odur.                                        |
| 2026-10-24 | Netleştirici sorular `config/process_types.json` içinde, seçenekli ve kişisel veri istemeyen sorular                  | Tutarlılık; cevaplar LLM'in serbest yorumuna bırakılmaz. **Soruların metni proje sahibinin onayını bekliyor.**                          |
| 2026-10-24 | Günlük LLM çağrı tavanı süreç içinde tutuluyor                                                                        | MVP için yeterli; birden çok sunucu örneğinde Redis'e taşınmalı.                                                                        |

## Değerlendirme (4. aşama)

| Tarih      | Karar                                                                                              | Gerekçe                                                                                                   |
| ---------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 2026-10-24 | Beklenen cevaplar yalnızca toplanan resmi kaynak metinlerinden; her unsurun yanında birebir alıntı | Kaynağı belli olmayan "doğru cevap", ölçülen sistemle aynı uydurma riskini taşır.                         |
| 2026-10-24 | Tüm vakalar proje sahibi doğrulayana kadar taslak; taslakla yapılan çalıştırmalar README'ye girmez | Proje sahibi kararı (2026-10-23): beklenen cevapları proje sahibi onaylar.                                |
| 2026-10-24 | Kapsam dışı vakalar ve "kaynak yetersiz" vakaları sette                                            | Her şeyi kapsam içi sayan veya her soruya cevap uyduran bir sistem yüksek puan almasın.                   |
| 2026-10-24 | Kapsama ölçümü programatik (eşdeğer ifadeler); uydurma ölçümü LLM yargıçla                         | Kapsama deterministik ve ücretsiz ölçülebilir; "kaynakta var mı" sorusu anlam karşılaştırması gerektirir. |
| 2026-10-24 | Yargıç modeli test edilen modelden farklı (varsayılan `claude-sonnet-5-5`)                         | Aynı modelin kendi çıktısını kayırma eğilimi. **Proje sahibi değiştirebilir.**                            |
| 2026-10-24 | Altyapı hataları puana katılmaz (`errors.jsonl`); ret, kesilme ve şema hatası ayrı durumlar        | Bir API kesintisi modelin başarısızlığı gibi görünmesin.                                                  |

## Kullanıcı arayüzü (5. aşama)

| Tarih      | Karar                                                                                                               | Gerekçe                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 2026-10-24 | Tarayıcı yapay zekâ servisine doğrudan bağlanmaz; web'in `/api/understand` ve `/api/roadmap` uçları üzerinden gider | Servis anahtarı tarayıcıya ulaşmaz; girdi doğrulama ve hız sınırı tek yerde uygulanır.             |
| 2026-10-24 | Hız sınırı: IP başına 10 dakikada 30 anlama, 10 yol haritası isteği (Redis; yoksa bellek)                           | Yol haritası en pahalı çağrı; kötüye kullanımı ve maliyet sıçramasını sınırlar.                    |
| 2026-10-24 | Servisten gelen yanıtlar web tarafında da şemayla doğrulanır                                                        | Beklenmeyen veya bozuk bir yanıt kullanıcıya hiç gösterilmez.                                      |
| 2026-10-24 | Netleştirici sorular tek turda sorulur; metinden çıkarılan cevaplar korunur                                         | "En fazla 3 soru" ilkesi; kullanıcıyı tekrar tekrar sorgulamamak.                                  |
| 2026-10-24 | Kaynakta ücret yoksa "Kaynakta belirtilmemiş; ilgili kurumdan öğreniniz" yazılır                                    | Boş bırakmak "ücretsiz" sanılabilir; tahmin yazmak ilkeye aykırı.                                  |
| 2026-10-24 | Kişisel bilgi maskelendiğinde kullanıcı bilgilendirilir                                                             | KVKK açısından şeffaflık.                                                                          |
| 2026-10-24 | PDF çıktısı tarayıcının yazdırma özelliğiyle (baskı CSS'i); kaynak adresleri çıktıda görünür                        | Sunucuda PDF üretmekten daha basit ve erişilebilir; kâğıtta da kaynak izlenebilir.                 |
| 2026-10-24 | Adım işaretleme bu aşamada yalnızca tarayıcı belleğinde                                                             | Kalıcı kayıt, hesap sistemiyle birlikte 6. aşamada.                                                |
| 2026-10-24 | Renk teması deniz yeşili; kırmızı-beyaz devlet teması bilerek kullanılmadı                                          | Kullanıcı resmi bir devlet sitesinde olduğunu sanmamalı.                                           |
| 2026-10-24 | Uçtan uca testler gerçek web sunucusu + sahte yapay zekâ servisiyle; her aşamada axe-core ile WCAG A/AA denetimi    | Tarayıcı → web → servis zinciri baştan sona sınanır; erişilebilirlik gerilemeleri CI'da yakalanır. |

## Açık konular

- **Araçların Satış, Devir ve Tescil Hizmetlerinin Yürütülmesi Hakkında Yönetmelik** henüz kaynak listesinde değil: Mevzuat Bilgi Sistemi'ndeki numarası güvenilir şekilde doğrulanamadı. Numara doğrulanınca `config/sources.yaml`'a eklenecek.
- **mevzuat.gov.tr geliştirme bilgisayarından erişilemiyor** (bağlantı zaman aşımı; site başka ağlardan açılıyor). Mevzuat kaynakları yayın ortamından (Railway) ilk çalıştırmada doğrulanacak.
- **Değerlendirme setinin doğrulanması:** `eval/VAKALAR.md` içindeki 23 beklenen unsur ve 92 vaka proje sahibinin onayını bekliyor. İlk ücretli çalıştırma için API anahtarı ve (yayın metrikleri için) indekslenmiş veritabanı gerekiyor.
- **Netleştirici soruların onayı:** Miras yoluyla araç devri (4 soru) ve mirasçılık belgesi (3 soru) için yazılan soru metinleri ve seçenekleri proje sahibinin onayını bekliyor.
- **EGM "Trafik Tescil Hakkında" sayfasının güncelliği:** Sayfa trafik tescil kuruluşunu başvuru yeri olarak gösteriyor; 2018'den beri araç satış/devir işlemleri noterlikte de yapılıyor. Kaynaklar arası olası çelişkiler 3. aşamada yanıtta uyarı olarak gösterilecek.

- **Giriş yapmamış kullanıcıların geri bildirimi:** Veri modelinde geri bildirim kayıtlı bir işleme (`user_processes`) bağlı. Giriş yapmadan yol haritası gören kullanıcıların da geri bildirim verebilmesi isteniyorsa 7. aşamada model genişletilmeli. Proje sahibinin kararı bekleniyor.
