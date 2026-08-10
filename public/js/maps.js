/* Maps — minimal, zero-key links to free/open mapping services.
   We never load a map SDK or use an API key; these are plain, public URL
   deep-links built from a masjid's stored latitude/longitude. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;

  // OpenStreetMap: map centered on the masjid.
  function osmUrl(lat, lon) {
    return "https://www.openstreetmap.org/?mlat=" + lat +
      "&mlon=" + lon + "#map=16/" + lat + "/" + lon;
  }

  // Waze: navigate to the point (keyless public link).
  function wazeUrl(lat, lon) {
    return "https://waze.com/ul?ll=" + lat + "," + lon + "&navigate=yes";
  }

  // Google Maps: plain directions link (keyless; no Maps API involved).
  function googleUrl(lat, lon) {
    return "https://www.google.com/maps/dir/?api=1&destination=" + lat + "," + lon;
  }

  // Apple Maps: point link.
  function appleUrl(lat, lon) {
    return "https://maps.apple.com/?ll=" + lat + "," + lon;
  }

  // Ordered list of {label, href} buttons for the masjid page.
  function buttons(lat, lon) {
    return [
      { label: "OpenStreetMap", href: osmUrl(lat, lon) },
      { label: "Waze", href: wazeUrl(lat, lon) },
      { label: "Google Maps", href: googleUrl(lat, lon) },
      { label: "Apple Maps", href: appleUrl(lat, lon) }
    ];
  }

  ME.maps = {
    osmUrl: osmUrl,
    wazeUrl: wazeUrl,
    googleUrl: googleUrl,
    appleUrl: appleUrl,
    buttons: buttons
  };
})();