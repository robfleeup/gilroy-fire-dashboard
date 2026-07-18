# Clean Start Instructions

1. Rename the old repository and old Render service rather than deleting them.
2. Create a new GitHub repository named `gilroy-fire-operations`.
3. Upload the contents of this folder to the repository root.
4. Create a new Render Web Service connected to the new repository.
5. Use `pip install -r requirements.txt` as the build command.
6. Use `gunicorn app:app` as the start command.
7. Use `/health` as the health check path.
8. Confirm `/health` reports version `1.0-static`.
9. Review the main dashboard design before adding any data.
