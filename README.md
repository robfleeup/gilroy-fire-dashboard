# Gilroy Fire Operations — Version 1.6

This release adds live-ready Current Operations using the OurGilroy public incident feed, NWS weather and alerts, verified First Due vegetation-fire activity, a Watch Duty live-map link, Smoke Ready California, and the current OES Engine 2614 Oregon deployment.

## Live sources
- OurGilroy public incident API: `https://ourgilroy.com/api/fire.php?view=incidents`
- National Weather Service API
- Watch Duty live map (linked)
- California Air Resources Board Smoke Ready California (linked)

The public incident feed refreshes every three minutes. If the source is unavailable, the page displays a transparent unavailable message rather than invented values.
