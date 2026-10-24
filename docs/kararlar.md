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

## Açık konular

- **Araçların Satış, Devir ve Tescil Hizmetlerinin Yürütülmesi Hakkında Yönetmelik** henüz kaynak listesinde değil: Mevzuat Bilgi Sistemi'ndeki numarası güvenilir şekilde doğrulanamadı. Numara doğrulanınca `config/sources.yaml`'a eklenecek.
- **mevzuat.gov.tr geliştirme bilgisayarından erişilemiyor** (bağlantı zaman aşımı; site başka ağlardan açılıyor). Mevzuat kaynakları yayın ortamından (Railway) ilk çalıştırmada doğrulanacak.
- **EGM "Trafik Tescil Hakkında" sayfasının güncelliği:** Sayfa trafik tescil kuruluşunu başvuru yeri olarak gösteriyor; 2018'den beri araç satış/devir işlemleri noterlikte de yapılıyor. Kaynaklar arası olası çelişkiler 3. aşamada yanıtta uyarı olarak gösterilecek.

- **Giriş yapmamış kullanıcıların geri bildirimi:** Veri modelinde geri bildirim kayıtlı bir işleme (`user_processes`) bağlı. Giriş yapmadan yol haritası gören kullanıcıların da geri bildirim verebilmesi isteniyorsa 7. aşamada model genişletilmeli. Proje sahibinin kararı bekleniyor.
