# Oracle Cloud Always Free kurulumu

Bu proje iki ücretsiz çalışma biçimi sunar:

- **Hibrit kurulum (önerilen):** Web arayüzü, zamanlayıcı ve veritabanı Oracle'da;
  AI modeli ise açık kalan kişisel bilgisayarınızdaki Ollama'da çalışır. Oracle'ın
  sınırlı işlemci ve belleği model yüküyle dolmaz.
- **Tek makine kurulumu:** Uygulama, zamanlayıcı ve Ollama aynı Oracle makinesinde
  çalışır. Küçük modelle kullanılabilir; ancak içerik üretimi belirgin şekilde yavaşlar.

Her iki düzende de zamanlayıcı hizmetinden yalnızca bir tane çalıştırılmalıdır.

## Hibrit kurulum: önce AI bilgisayarını hazırlayın

1. Kişisel bilgisayarınızda Ollama ve `gemma3:4b` modeli çalışır durumda kalsın.
2. Kişisel bilgisayar ve Oracle makinesinde aynı ücretsiz Tailscale hesabını
   kullanın. Bu ağ, AI bağlantısını internete açmadan iki makine arasında özel
   olarak taşır.
3. Kişisel bilgisayarda Ollama'yı Tailscale ağından erişilebilir hale getirin ve
   güvenlik duvarında sadece Tailscale ağına `11434` erişimi tanıyın. Genel
   internete port açmayın.
4. Oracle'daki `.env` dosyasında `OLLAMA_HOST` değerini bilgisayarınızın
   Tailscale adresiyle değiştirin. Örnek: `OLLAMA_HOST=http://100.64.0.10:11434`.
5. Oracle'da aşağıdaki dosyayla başlatın:

```sh
docker compose -f compose.hybrid.yaml up -d --build
docker compose -f compose.hybrid.yaml ps
docker compose -f compose.hybrid.yaml logs -f app worker
```

Hibrit düzende bilgisayar kapalıysa haber toplama ve panel çalışmaya devam eder;
yalnızca yeni AI üretimleri bilgisayar tekrar açılana kadar bekler. Sistem, bu
geçici hataları kontrollü biçimde yeniden dener.

## Tek makine kurulumu

## 1. Oracle makinesini hazırlayın

Ubuntu tabanlı bir Always Free A1 makinesi oluşturun. Alan adınızın `A` kaydını
makinenin genel IP adresine yönlendirin. Oracle güvenlik listesi ve makinenin
güvenlik duvarında sadece şunları açın:

- `22/tcp`: yalnızca kendi sabit IP adresinizden SSH için
- `80/tcp`: HTTP ve TLS doğrulaması için
- `443/tcp` ve `443/udp`: HTTPS için

Makineye Docker Engine ile Docker Compose eklentisini kurun. Bu proje ARM64
makinede çalışacak şekilde standart çoklu mimari imajları kullanır.

## 2. Gizli ayarları oluşturun

Proje klasöründe örnek dosyayı kopyalayın ve içindeki tüm `replace-with-...`
değerlerini değiştirin:

```sh
cp .env.example .env
```

`SECRET_KEY` ve `ADMIN_PASSWORD` için uzun ve birbirinden farklı rastgele
değerler kullanın. `.env` dosyasını Git'e eklemeyin.

## 3. Başlatın

```sh
docker compose up -d --build
docker compose ps
docker compose logs -f app worker
```

İlk açılışta `ollama-init`, `.env` içindeki `OLLAMA_MODEL` modelini indirir.
Bu işlem model boyutu ve makinenin bağlantısına göre zaman alır. Sağlık kontrolü
başarılı olduğunda aşağıdaki adres JSON yanıtı vermelidir:

```text
https://alan-adiniz/api/health
```

Caddy, alan adı için TLS sertifikasını otomatik alır ve yalnızca `80` ile `443`
portlarını dışarı açar. FastAPI hizmeti doğrudan internete açılmaz.

## 4. Kalıcı veri ve yedekler

`app_data` Docker biriminde SQLite veritabanı tutulur. `backup` hizmeti ilk
açılışta ve ardından her 24 saatte bir tutarlı SQLite yedeğini `backup_data`
birimine alır. Yedekleri görüntülemek için:

```sh
docker compose exec backup ls -lh /backups
```

Bu yedekler aynı sanal makinededir. Önemli veriler için yedekleri düzenli olarak
makine dışına (örneğin kişisel bilgisayarınıza veya Object Storage'a) da kopyalayın.
`docker compose down -v` komutunu kullanmayın; kalıcı veritabanı, modeller ve
sertifikalar da silinir.

## 5. Güncelleme

```sh
git pull
docker compose up -d --build
docker compose logs -f app worker
```

Veritabanı adresi `DATABASE_URL` ile değiştirilebilir. Bu nedenle ileride
PostgreSQL'e geçildiğinde uygulama kodunu değiştirmek gerekmez; Docker bağımlılık
dosyası PostgreSQL sürücüsünü de içerir. Mevcut tek makine kurulumu SQLite + WAL
modunu kullanır ve eşzamanlı erişim için bekleme süresi tanımlar.
