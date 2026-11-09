/* Геолокация: Telegram LocationManager, запасной navigator.geolocation. */
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const lm = tg && tg.initData && tg.LocationManager;

  function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371008.8, r = x => x * Math.PI / 180;
    const a = Math.sin(r(lat2 - lat1) / 2) ** 2 + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
  const DENIED = 'Нет доступа к геопозиции. Разрешите её в настройках Telegram и телефона, затем повторите.';

  function viaTelegram() {
    return new Promise((resolve, reject) => {
      lm.init(() => {
        if (!lm.isLocationAvailable) return reject(new Error('Геолокация недоступна на этом устройстве.'));
        lm.getLocation(loc => {
          if (!loc) { try { lm.openSettings(); } catch (e) { /* нет API */ } return reject(new Error(DENIED)); }
          resolve({ lat: loc.latitude, lon: loc.longitude, accuracy: loc.horizontal_accuracy || 9999 });
        });
      });
    });
  }
  function viaBrowser() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error('Геолокация недоступна.'));
      navigator.geolocation.getCurrentPosition(
        p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }),
        () => reject(new Error(DENIED)), { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
    });
  }
  window.geo = {
    haversine,
    getPosition: () => (lm ? viaTelegram() : viaBrowser()),
  };
})();
