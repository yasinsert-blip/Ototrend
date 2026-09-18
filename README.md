# OtoTrend AI Newsroom

OtoTrendTR'nin haber toplama, AI editör, Instagram taslağı ve Telegram
bildirim sistemidir. Bu depo program kodunu ve marka görsellerini içerir;
parolalar, Telegram bilgileri, yerel haber veritabanı ve üretilmiş haber
görselleri özellikle depoya eklenmez.

## Yeni bilgisayarda hızlı kurulum (Windows)

Gerekenler:

- Git
- Python 3.11 veya daha yeni
- [Ollama](https://ollama.com/) (ücretsiz yerel AI için)

Komut İstemi veya PowerShell'de aşağıdaki adımları uygulayın:

```powershell
git clone https://github.com/yasinsert-blip/Ototrend.git OtoTrend-AI-Newsroom
cd OtoTrend-AI-Newsroom
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull gemma3:4b
```

Ardından `.env` dosyasını açın ve aşağıdaki değerleri kendi bilgilerinizle
doldurun:

- `SECRET_KEY`: uzun ve rastgele bir metin
- `ADMIN_USERNAME` ve `ADMIN_PASSWORD`: yeni bilgisayardaki yönetici girişi
- `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID`: mevcut Telegram bot bilgileriniz
- Yerel kurulum için `DATABASE_URL=sqlite:///news.db`
- `AI_PROVIDER=ollama` ve `OLLAMA_HOST=http://127.0.0.1:11434`

Programı başlatmak için:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765
```

Tarayıcıdan `http://127.0.0.1:8765` adresini açın. İlk açılışta veritabanı
ve kaynak listesi otomatik oluşur. Yerel haber geçmişini de taşımak
isterseniz eski bilgisayardaki `news.db` dosyasını, uygulama kapalıyken, yeni
bilgisayardaki proje klasörüne kopyalayın. Bu dosya GitHub'a yüklenmez.

AI kuyruğu varsayılan olarak yalnızca son 24 saatte gelen haberleri işler.
Puanı 8 ve üzeri olanlar editör incelemesine düşer; bu eşikleri `.env`
dosyasındaki `AI_QUEUE_MAX_AGE_HOURS` ve `AI_REVIEW_MIN_IMPORTANCE`
değerleriyle değiştirebilirsiniz.

Bir kaynak art arda üç kez hata verirse otomatik olarak pasife alınır. Kaynak
Yönetimi ekranındaki “yeniden etkinleştir” düğmesiyle tekrar açılabilir.

## Editör ve kaynak yönetimi

- Editörde arama, marka, kategori, durum ve en düşük önem puanı birlikte
  kullanılabilir. Arama, özgün/Türkçe başlıkta, özette ve kaynak adında yapılır.
- Haberleri en yeni, en eski veya en önemli önce sıralayın. Sayfada 20, 50 veya
  100 haber gösterilir; sayfa değiştirirken filtreler korunur. Toplu işlemler
  yalnızca o sayfada seçtiğiniz haberleri etkiler.
- Kaynaklarda ad, marka veya adresle arama yapın; aktif, pasif veya kontrol
  gereken kaynakları süzün. Son tarama, son başarı ve hata ayrıntıları listede
  görünür. Tarihler tarayıcınızın yerel saatine göre gösterilir.
- Duraklat, kaynağı sonraki taramalardan çıkarır; devam eden tarama tamamlanabilir.
  Etkinleştir, ayarları doğrular ve hata sayacını sıfırlar. Haber geçmişi korunur.
- Kaynak eklerken RSS adresiniz varsa Genel RSS seçin. Özel okuyucular kendi
  sitelerini okur; RSS adresleri boş bırakılabilir. Kaynak düzenleme, resmî
  kaynak ve marka bilgisini korur.

## Otomatik çalışma ve saklama

### Türk kaynaklarından Telegram bildirimi

Bu sürümden sonra yeni kaydedilen Türk kaynak haberleri ayrı ve kalıcı Telegram
kuyruğuna alınır. Kaynak dili `tr`, ülkesi Türkiye/TR veya sitesi `.tr` olmalıdır;
tanımlı özel okuyucu adları da eşleştirilir (Motor1TR, DonanimHaber gibi). Yabancı
kaynağın AI ile Türkçeye çevrilmiş olması bu kuralı etkinleştirmez.

Özgün başlık ve bağlantı gönderilir; AI sonucu/önem puanı, doğruluk uyarısı,
gruplama ve kısa içerik engeli bu kaynak bildirimini durdurmaz. AI üretimiyle aynı
bildirimin ikinci kez gönderilmesi önlenir. Mevcut arşiv otomatik olarak kuyruğa
alınmaz ve yabancı kaynakların bildirim davranışı değişmez.

Zamanlayıcı kuyruğu dakikada bir, tur başına en fazla 10 haberle kontrol eder.
Başarısız gönderimler 1 dakikadan başlayıp en fazla 60 dakikaya kadar artan
aralıklarla yeniden denenir; süreç yeniden başlasa da kuyruk korunur. Silinmiş
kayıtlar gönderilmez. Telegram/internet kesintileri teslimatı geciktirebilir.
Telegram'ın mesajı kabul edip yanıtın kaybolduğu belirsiz ağ durumlarında tekrar
bildirim oluşabilir; mutlak tek teslim garantisi yoktur. Gönderim hatası haber
detayında görünür. Bu bildirim kaynak bilgisidir, AI doğruluk onayı değildir.

Windows'ta oturum açınca arka planda çalıştırmak için
`scripts/start_ototrend.ps1` kullanılabilir. Haber saklama politikası varsayılan
olarak 90 gün sonra arşivler; bir yılı geçen arşivleri, önce yedek alarak,
temizler.

## Sunucu kurulumu

Docker ve sunucu kurulumu için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasındaki
adımları izleyin. Sunucuda `.env` içindeki `DATABASE_URL` değeri
`sqlite:////data/news.db` olarak kalmalıdır.

## Haber gruplama ve AI ön eleme

Yeni kayıtlar silinmeden, son 48 saatteki en fazla 2.000 ana kayıtla karşılaştırılır.
Yalnızca yeterince uzun ve aynı başlıklar (büyük/küçük harf, boşluk ve bilinen
kaynak son eki dışında değişiklik olmadan) gruplanır. Farklı dillerdeki veya
yeniden yazılmış başlıkları anlamsal olarak birleştirmez. Varsayılan filtresiz
haber listesinde ana kayıt görünür; editör tablosundaki “ek kaynak” bölümü diğer
kayıtlara erişim sağlar. Kaynak/durum/arama filtreleri tüm kayıtları gösterir.

Kaynak metni en az 250 karakter, 40 kelime ve başlığa ek en az 12 farklı kelime
içermiyorsa AI üretimi atlanır. Bu eşik doğruluk garantisi değildir; başlıktan
ayrıntı uydurma ve gereksiz işlem riskini azaltır. Otomatik atlama gerekçesi
“AI atlandı” filtresinde görünür. Tekli ve toplu manuel üretim ile Instagram
üretimi de yetersiz kaynak metninde durur; mevcut editör metinleri silinmez.
Manuel olarak seçilen yeterli içerikli bir ek kaynak yeniden işlenebilir.

Mevcut haber arşivi topluca değiştirilmez. Yeni içe alımlar ve otomatik kuyrukta
sırası gelen kayıtlar kontrol edilir. Kod değişiklikleri uygulama bir sonraki
başlatılışında devreye girer; gerekli ek alan başlangıçta otomatik oluşturulur.

## Türkiye odaklı haber değeri

### Editör çalışma alanları ve karşılaştırma

#### Benzer haber önerileri

Haber detayında orijinal/mevcut Türkçe başlıklar karşılaştırılarak en fazla beş
öneri gösterilir. Arama, kaydın çevresindeki 72 saat içinde daha önce eklenen
en fazla 500 ana kayıtla sınırlıdır. Farklı diller ancak mevcut çeviriler ortak
başlık karşılaştırmasına izin veriyorsa eşleşir; yeni çeviri veya model çağrısı
yapılmaz. Gösterilen puan aynı olay olma olasılığı değil başlık yakınlığıdır.

Öneri görüntülemek hiçbir kaydı değiştirmez. Onay kutusu ve “grupla” işlemi
gereklidir; sayı farklılıkları uyarı olarak gösterilir. Ana kayıt daha önce
eklenen haber olur. Yayın sürecindeki kayıtlar ve mevcut alt kaynakları olan
gruplar bu yolla taşınamaz. “Gruptan ayır” metinleri değiştirmeden bağlantıyı
kaldırır; otomatik kuyruktaki ayrılan haber manuel incelemeye bırakılır.

#### Çalışma alanları

Editörde üç çalışma alanı bulunur: “Önemli haberler” son 48 saatte alınan ve
haber değeri en az 60 olan kayıtları; “İnceleme bekleyenler” AI taslaklarını,
manuel kontrol durumlarını ve doğruluk uyarılarını; “Yayıma hazır” yalnızca
Instagram hazır/planlanmış, doğruluk uyarısı olmayan kayıtları gösterir.
Yayımlanan ve arşivlenen kayıtlar bu alanların dışında kalır, “Tüm haberler”den
erişilebilir. Bölüm seçimi filtreleme ve sayfalama sırasında korunur.

Haber editöründe kaynak metni solda salt okunur, Türkçe taslak sağda düzenlenebilir
gösterilir. 850 piksel altındaki ekranlarda alt alta geçer. Kaydetme işlemi kaynak
metnini değiştirmez ve yayın başlatmaz. Genel istatistikler açılır bölümde tutulur.

### Puanlama

Yeni kayıtlar AI çağrısı olmadan 0–100 arasında puanlanır. Başlangıç puanı 20;
otomotiv bağlantısı +15, Türkiye bağlantısı +25, fiyat/vergi +15, yeni model +10,
yatırım/üretim +15, güvenlik/sektör gelişmeleri +15 puan getirir. Başlıkta belirgin
webinar/sponsorlu içerik işaretleri −60; otomotiv bağlantısı olmayan belirli konu
dışı başlıklar −20 puan alır. Toplam 0–100 aralığına sınırlandırılır.

Editörde “Türkiye öncelikli” bağlantısı veya “Türkiye odaklı haber değeri”
sıralaması kullanılabilir. Puan gerekçeleri kayıt üzerinde açılır. Mevcut
varsayılan tarih sıralaması ve AI önem puanı değiştirilmez. Otomatik AI kuyruğu
uygun kayıtları haber değerine göre işler; düşük puan tek başına silme veya
kalıcı işlem engeli değildir. Kuyruk yenilenirken son 48 saatin puansız en fazla
2.000 kaydı tamamlanır; eski arşiv ve editör metinleri değiştirilmez.

Kurallar Türkçe/İngilizce anahtar kelimelere dayanır; haber değeri veya konu
uygunluğu için kesin karar değildir. Tanınmayan başlıklar nötr kalır. Puan
doğruluk kontrolünden ayrıdır ve yeni bir AI/model aboneliği gerektirmez.

## Yerel model karşılaştırması

### Kaynak tutarlılığı kontrolü

Haber AI çıktısı ve Instagram taslakları ek model çağrısı olmadan kaynak
başlığı/metniyle karşılaştırılır. Kaynakta bulunmayan marka/model alanları,
yaygın marka adları ve alfanümerik model kodları, sayılar, fiyat–para birimi
eşleşmeleri ve İngilizce/Türkçe açık gün–ay tarihleri uyarı oluşturur.
Şüpheli çıktı saklanır, `editor_review` durumuna yönlendirilir ve otomatik
Telegram bildirimi gönderilmez. Uyarı liste ve detay ekranında görünür.

Bu bir olgusal doğruluk garantisi değildir: aynı sayının yanlış olaya bağlanması,
olumsuzluk, kapsam dışında kalan marka/model yazımları ve göreli tarihler kaçabilir.
Yuvarlama, farklı tarih/para yazımları veya birim dönüşümleri yanlış alarm verebilir.
Editör kontrolü gereklidir; manuel yayın kararı otomatik olarak engellenmez.
Eski taslaklar topluca yeniden işlenmez. Yeni kontrol bir sonraki uygulama
başlatılışından sonra üretilen çıktılara uygulanır.

### Model karşılaştırmasını çalıştırma

`scripts/compare_local_models.py`, haber veritabanını yalnızca okuma modunda açar
ve farklı kaynaklardan 20 haberi `logs/model-comparison/samples.json` içinde
sabitler. Aynı örneklerle iki modeli sırayla çalıştırmak için:

```powershell
.venv\Scripts\python.exe -X utf8 -u scripts\compare_local_models.py --model gemma3:4b
.venv\Scripts\python.exe -X utf8 -u scripts\compare_local_models.py --model qwen3.5:4b
```

Modeller önceden Ollama'ya indirilmiş olmalıdır. Araç `.env` veya haber kayıtlarını
değiştirmez, yayın yapmaz ve dış AI servislerine haber göndermez. Tek denemedeki
süre, JSON/alan yapısı ve mevcut temel Türkçe kontrolünün sonuçlarını kaydeder;
bu kontrol olgusal doğruluk veya editoryal kalite puanı değildir. Qwen'in düşünme
modu kapalıdır. Model yükleme süresi ayrıca kaydedilir. Çalışan uygulama
durdurulmadığından arka plan yükü süreleri etkileyebilir. Özellikle 8 GB RAM'li
bilgisayarlarda bellekte kalan iki model test sırasında yavaşlamaya yol açabilir.

Başarılı kaydedilmiş örnekler aynı komut yeniden çalıştırıldığında atlanır.
Yeni bir karşılaştırma için farklı bir `--output logs/model-comparison-YENI`
klasörü kullanın. Raporlar ve haber örnekleri Git'e dahil edilmez.

### Windows çevrimdışı kurulum

Windows 10/11 x64 kurulum paketi Python, Chromium, CPU Ollama ve Gemma 3 4B
bileşenlerini birlikte taşır. GitHub Releases paketinin **bütün dosyalarını**
aynı klasöre indirin; yalnızca Setup.exe yeterli değildir. Kurulum, ilk açılış
ve imzalı otomatik güncelleme açıklamaları: [Windows kurulum kılavuzu](installer/README.md).
Kişisel ayarlar ve haber veritabanı dağıtım paketine dahil edilmez.

### AI süreleri ve işlem durumu

Ollama bağlantısında `AI_TIMEOUT` (varsayılan 120 saniye) uygulanır;
bağlantı kurma sınırı 10 saniyedir. Bu ağ bekleme sınırıdır, tüm işlemin
kesin bitiş süresi değildir. Kalite kontrolü için ikinci çağrı toplam süreyi
uzatabilir; zaman aşımı Ollama sunucusundaki hesabın durduğunu garanti etmez.
Otomatik başarısız işlemler mevcut 15/30 dakika beklemeli, en fazla üç
denemeli kuyruğa döner. Başlangıçta yarım kalan işlemler de deneme sınırına
dahil edilir (ilk yeniden deneme beklemesi 15 dakika).

Yeni işlemlerin toplam AI işlem süresi, model süresi ve girdi karakter sayısı
kaydedilir. Kayıttan son denemeye geçen süre önceki denemeleri de içerir;
saf kuyruk bekleme süresi değildir. Eski kayıtların ölçümleri boş kalır.
Liste ve detayda AI/Telegram durumları sayfa yenilendiğinde güncellenir.
Türk kaynak bildirimleri AI sonucunu beklemeyen ayrı kuyrukta kalır.
