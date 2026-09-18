# Windows çevrimdışı kurulum ve imzalı güncelleme

Bu klasör Setup.exe derleyicisini ve kurulu sürümün otomatik güncelleyicisini içerir.
Hedef: Windows 10 22H2/11 x64, kullanıcı başına kurulum; mevcut geliştirme
kurulumuna dokunmadan ayrı veri dizini.

## Paket bileşenleri

- Bağımsız Python çalışma ortamı ve requirements.windows.txt bağımlılıkları.
- Playwright ile aynı sürümün Chromium motoru; yalnızca Python paketi yeterli değil.
- Ollama Windows çalışma ortamı ve gemma3:4b manifestinde başvurulan model dosyaları.
- Uygulama, şablonlar, statik dosyalar, kaynak başlangıç kayıtları.
- Python, Chromium, Ollama, Python paketleri ve Gemma lisans/NOTICE metinleri.
- İlk açılışta yeni yönetici parolası ve Telegram ayarlarının yerel olarak alınması.

Kaynak arşivi çalışma ortamının yerine geçmez. Mevcut .venv başka bilgisayara
kopyalanarak taşınabilir Python elde edilemez. .env, SQLite dosyaları, geçmiş
haberler, günlükler, yedekler ve üretilen görseller dağıtıma dahil edilmez.

## Güncelleme güvenliği

1. Yalnızca yasinsert-blip/Ototrend kararlı Releases sürümleri.
2. Sürüm, dosya boyutu ve SHA-256 içeren imzalı manifest; doğrulama anahtarı
   uygulamada sabitlenir. Özel imzalama anahtarı depoya veya setup'a konmaz.
3. İndirilen sürüm ayrı dizine açılır; ZIP yol geçişleri ve sembolik bağlantılar
   reddedilir. Eksik/bozuk/imzasız paket çalıştırılmaz.
4. Çalışan AI/bildirim işleri güvenli şekilde tamamlandıktan sonra SQLite backup
   API ile yedek alınır. Kullanıcı ayarları ve veritabanı paket tarafından ezilmez.
5. Yeni sürüm uygulama yükleme ve şema kontrolünden geçmeden eski sürüm silinmez. Şema geri dönüşü
   gerektiğinde yalnızca o güncellemeye ait yedekle ve uygulama kapalıyken yapılır.
6. Ağ yoksa çalışan sürüm kullanılmaya devam eder. Model değişmediyse yeniden
   indirilmez. Geliştirme kopyasında otomatik güncelleme varsayılan olarak kapalıdır.

## Yayın kontrol listesi

- Temiz Windows makinede internet kapalı kurulum ve açılış testi.
- Telegram ayarları olmadan ilk kurulum ekranı; ayarlanmadan bildirim yapılmaması.
- Eski sürümden geçiş, veri korunması, bozuk imza ve kesilen indirme testleri.
- GitHub yayın yetkisi, güncelleme imzalama anahtarının güvenli saklanması.
- Gemma dağıtım koşulları ve üçüncü taraf lisanslarının pakete dahil edilmesi.
- GitHub Release varlıkları tek dosyada 2 GiB altında kalmalı; tam paket
   Setup.exe ve beraberinde taşınan veri parçaları olarak yayımlanabilir.

Kaynaklar:
https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
https://ai.google.dev/gemma/terms
https://docs.ollama.com/windows

## Başka bilgisayara kurma

GitHub Releases sürümündeki bütün dosyaları aynı klasöre indirin ve Setup.exe'yi
çalıştırın. Setup.exe tek başına yeterli değildir. Model dört parçadır; bunları
elle birleştirmeyin. Başlat menüsünden OtoTrend AI'ı açıp ilk kurulum ekranında
yönetici adı ve yeni parolanızı girin. Telegram bilgileri boşsa bildirim gönderilmez.
Telegram ayarlarını sonradan değiştirmek için uygulamayı kapatıp kurulumun
`data/.env` dosyasını düzenleyin. Bu dosyayı paylaşmayın.

Kurulum `%LOCALAPPDATA%/OtoTrendAI` dizinindedir; kişisel dosyalar `data` altında
saklanır. Başlat menüsündeki **OtoTrend AI - Kapat** ile arka plan taramasını
durdurun. Yalnızca tarayıcıyı kapatmak taramayı durdurmaz. Eski geliştirme kopyası
8765 portunu kullanıyorsa önce onu kapatın.

Python 3.13.12, Chromium, CPU-only Ollama 0.34.0 ve Gemma 3 4B dahildir.
GPU hızlandırması dahil değildir. 8 GB RAM ve en az 15 GB boş alan önerilir.
Haber taraması, Telegram ve güncelleme indirmeleri internet gerektirir;
çevrimdışı kurulum çevrimdışı haber toplama anlamına gelmez.
Windows yayıncı sertifikası olmadığı için SmartScreen uyarısı görülebilir.
Paket imzası Windows Authenticode sertifikasının yerine geçmez.

Güncellemeler açılıştan sonra ve altı saatte bir kontrol edilir. İmzası doğrulanan
güncelleme arka planda indirilir, **sonraki uygulama açılışında** otomatik uygulanır.
Tarayıcı yenilemek yeniden başlatma değildir. Değişmeyen model ve tarayıcı
bileşenleri yeniden indirilmez. Geliştirme kopyası otomatik güncellenmez.

## Bakım ve test

Özel imza anahtarı `installer/private/release-key.dpapi` içinde Windows hesabına
bağlı şifrelenir; GitHub'a ve pakete dahil edilmez. Dosya veya Windows profili
kaybolursa aynı anahtarla yayın yapılamaz. Yayın bilgisayarının/profilinin güvenli
yedeği önemlidir. Public key `installer/desktop/public-key.xml` dosyasıdır.

`scripts/build_windows_release.py --version X.Y.Z` yeni, imzalı paket oluşturur;
vendor Python, Chromium ve yerel model dosyaları önceden hazırlanmalıdır.
İlk derleme lisans ve CSS/JS dosyalarını indirir; kurulum bunları indirmez.
`scripts/verify_windows_install.py --release dist/vX.Y.Z --target build/test-X.Y.Z`
yalıtılmış test kurulumu, dış ağ istekleri engellenmiş editör testi ve paketli
Ollama model kayıt kontrolü yapar. Bu ayrı fiziksel bilgisayar veya temiz Windows
sanal makine testi değildir; gerçek veritabanına ve Telegram bilgilerine dokunmaz.

Yayın betiği `scripts/publish_windows_release.py --directory dist/vX.Y.Z --commit TAM_COMMIT`
önce GitHub taslağına yükler. Aynı komuta `--publish` eklemek uzak dosya özetlerini
kontrol ettikten sonra sürümü herkese açar. Kaynak kod ayrıca gönderilmelidir.
