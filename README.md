# Gilroy Fire Operations Dashboard — Clean Rebuild

This repository was rebuilt from a blank folder. Only verified department data and image assets were carried forward.

## Deploy to Render
1. Replace the contents of the GitHub repository with every file and folder in this package.
2. Commit the replacement.
3. In Render, choose **Manual Deploy → Clear build cache & deploy**.
4. The health check is `/health`.

## Editable data
- Historical metrics and unit tiles: `data/historical.json`
- Mutual aid: `aid_received_ytd` and `aid_given_ytd`
- Deployments: `deployments` array

## Live sources
The backend tries the public PulsePoint endpoint first and then the OurGilroy public incident feed as a fallback. Weather and alerts use the National Weather Service.
