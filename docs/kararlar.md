# Karar Kaydı

Ürün kararları proje sahibi Aslı Zeynep Aydemir tarafından verilir. Teknik varsayılanlar bu dosyada gerekçeleriyle not edilir.

## Ürün kararları

| Tarih      | Karar                                                                        | Gerekçe                                                                                    |
| ---------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| 2026-10-23 | Proje adı **Evrakyol**                                                       | Kısa, Türkçe ve ürünün işlevini anlatıyor.                                                 |
| 2026-10-23 | Türkiye Noterler Birliği (tnb.org.tr) izin listesine dahil                   | Araç devri ve mirasçılık belgesi noterde yapılıyor; alan adı `.gov.tr` olmasa da resmi kaynak. |
| 2026-10-23 | Embedding modeli kendi sunucumuzda çalışır (`BAAI/bge-m3`)                   | Ücretsiz, Türkçe'de güçlü; kullanıcı metni embedding için üçüncü tarafa gönderilmez.       |
| 2026-10-23 | Değerlendirme setinin beklenen cevaplarını proje sahibi onaylar              | Yapay zekânın kendi ürettiği cevapla ölçülmesi döngüsel ve yanıltıcı olur.                  |
| 2026-10-23 | Web (Next.js) + yapay zekâ servisi (FastAPI) iki ayrı parça                   | Veri toplama, embedding ve değerlendirme araçları Python ekosisteminde daha olgun.          |
| 2026-10-23 | Netleştirici sorular işlem türüne özgü, önceden tanımlı alanlardan seçilir   | Tutarlı sorular, kişisel veri istenmemesi, aynı durum için önbelleğe alınabilir yanıt.      |

## Teknik varsayılanlar

| Tarih      | Karar                                                                                  | Gerekçe                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 2026-10-23 | Postgres iki şemaya ayrıldı: `app` (Prisma) ve `kb` (Alembic)                          | İki ORM'in aynı tabloları değiştirip birbirinin migration'larını bozmasını önler.                              |
| 2026-10-23 | İşlem türleri `config/process_types.json` dosyasında tek kaynaktan                      | Web seed'i ve API sınıflandırıcısı aynı listeyi kullanır; listeler birbirinden kopamaz.                         |
| 2026-10-23 | Tek `.env` dosyası kök klasörde                                                        | Web, API ve Docker Compose aynı ayarları okur. API, `postgresql://` adresine sürücüyü kendisi ekler.           |
| 2026-10-23 | Anahtar kelime araması Postgres `turkish` tam metin yapılandırmasıyla (üretilmiş sütun) | Ek bir arama servisi gerektirmez; vektör aramasıyla aynı sorguda birleştirilebilir (hibrit arama).            |
| 2026-10-23 | Vektör indeksi HNSW + kosinüs uzaklığı                                                 | Küçük-orta veri boyutunda yüksek isabet, ek ayar gerektirmez.                                                  |
| 2026-10-23 | Varsayılan LLM: Anthropic Claude (`LLM_PROVIDER`, `LLM_MODEL` ile değiştirilebilir)     | Proje sahibi sağlayıcı belirtmedi; katman sağlayıcıdan bağımsız tasarlanacak (3. aşama).                       |
| 2026-10-23 | Barındırma: Neon (Postgres + pgvector), Railway (API), Vercel (web)                    | Neon pgvector'ü hazır sunar; Railway Dockerfile ile çalışır.                                                   |
| 2026-10-23 | Node 24, Next.js 16, Prisma 7 (driver adapter), Python 3.13, SQLAlchemy 2.1            | Geliştirme başladığında güncel kararlı sürümler.                                                               |

## Açık konular

- **Giriş yapmamış kullanıcıların geri bildirimi:** Veri modelinde geri bildirim kayıtlı bir işleme (`user_processes`) bağlı. Giriş yapmadan yol haritası gören kullanıcıların da geri bildirim verebilmesi isteniyorsa 7. aşamada model genişletilmeli. Proje sahibinin kararı bekleniyor.
