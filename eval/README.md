# Değerlendirme

Bu klasör, Evrakyol'un soru anlama ve yol haritası üretiminin ölçüldüğü vaka setini, çalıştırma çıktılarını ve tarihli raporları içerir. README'deki metrikler yalnızca buradaki raporlardan alınır.

| Dosya / klasör   | İçerik                                                                               |
| ---------------- | ------------------------------------------------------------------------------------ |
| `cases.yaml`     | Vaka seti ve beklenen unsur kütüphanesi (her unsur kaynağından alıntıyla)            |
| `VAKALAR.md`     | Proje sahibinin onayı için otomatik üretilen okunabilir döküm                        |
| `runs/<etiket>/` | Çalıştırma çıktıları: `run.json`, `results.jsonl`, `errors.jsonl`, `traces/`         |
| `raporlar/`      | Tarihli Markdown raporlar; `son.json` README'nin kullandığı en son doğrulanmış sonuç |

## Vaka seti

- **92 vaka:** MVP'deki 8 işlemin her biri için 10 vaka ve 12 kapsam dışı vaka.
- **Yol haritası vakaları:** Miras yoluyla araç devri ve mirasçılık belgesi için 20 vaka. Kalan 6 işlemin yol haritası beklentileri, kaynakları eklendiğinde (8. aşama) yazılacak.
- **Özel vakalar:** Zor sınırlar (ör. "babamdan kalan ev" bir tapu işlemi, kapsam dışı), gündelik dil ve Türkçe karaktersiz yazım, kişisel veri içeren metin, istem enjeksiyonu denemesi ve kaynakların cevap **vermediği** sorular (sistem uydurmamalı).
- **Beklenen cevapların kaynağı:** Yalnızca `config/sources.yaml`'daki resmi kaynakların metinleri. Her vaka proje sahibi doğrulayana kadar `dogrulandi: false` olarak kalır; doğrulanmamış vakalarla yapılan çalıştırmalar raporda uyarıyla gösterilir ve README'ye aktarılmaz.

## Metrikler

| Metrik                                                      | Nasıl ölçülür                                                                                                              |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Doğru işlem sınıflandırma                                   | Tahmin edilen işlem kodu = beklenen (kapsam dışı dahil)                                                                    |
| Kapsam dışı duyarlılık / kesinlik                           | Kapsam dışı vakaların ne kadarı yakalandı / "kapsam dışı" denenlerin ne kadarı gerçekten öyle                              |
| Beklenen unsurların / evrakların kapsanması                 | Beklenen her unsurun eşdeğer ifadelerinden biri yol haritası metninde geçiyor mu                                           |
| Kaynak gösterilen adım oranı                                | Çıktıdaki adımların en az bir kaynağa bağlı olma oranı                                                                     |
| Kaynağa karşı doğrulanan adım oranı                         | Modelin ürettiği adımlardan alıntısı kaynakta bulunanların oranı                                                           |
| Uydurma içermeyen yol haritası / desteklenmeyen iddia oranı | Ayrı bir LLM yargıç, yol haritasını tek tek iddialara böler ve her birini modele verilen kaynak parçalarıyla karşılaştırır |
| Netleştirme cevabı çıkarma                                  | Metinde açıkça verilen bilgilerin doğru cevaba dönüştürülme oranı                                                          |
| Kişisel veri sızıntısı                                      | Vakadaki kişisel verilerden biri maskelenmeden LLM isteğine girdi mi                                                       |

- **Yol haritası metrikleri:** Sınıflandırma hatasına karışmasın diye beklenen işlemle üretilir; iki yetenek ayrı ölçülür.
- **Uydurma yargıcı:** Test edilen modelden farklı bir modeldir (varsayılan `claude-sonnet-5-5`).
- **Altyapı hataları:** API hatası, zaman aşımı gibi durumlar `errors.jsonl`'a yazılır ve puana katılmaz. Modelin reddetmesi (`refusal`), yanıtın kesilmesi (`truncated`) ve şemaya uymayan yanıt (`schema_failure`) ise ayrı durumlar olarak sayılır.
- **Güven aralığı:** Her metrik %95 güven aralığıyla raporlanır. 20 yol haritası vakası ve tek tekrarla aralık yaklaşık ±20 puandır; daha dar aralık için `--reps 2` veya `--reps 3` kullanılır.

## Çalıştırma

```bash
cd services/api
python -m app.evaluation check                                  # vaka setini denetle (ücretsiz)
python -m app.evaluation review                                 # VAKALAR.md'yi yeniden üret
python -m app.evaluation run --label taban                      # tam çalıştırma (ücretli, ANTHROPIC_API_KEY gerekir)
python -m app.evaluation run --label deneme --retriever memory --only miras_arac_01 mirascilik_01
```

Aynı etiketle yeniden çalıştırma kaldığı yerden devam eder. Farklı model, yargıç, arama türü veya değişmiş vaka dosyasıyla aynı etiket kullanılamaz.
