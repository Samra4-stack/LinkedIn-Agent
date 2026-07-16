# Support Gallery Image Uploads

Adding support for gallery uploads requires bypassing Vercel's strict 4.5MB upload limit, as modern phone cameras easily produce 5-10MB photos.

## Proposed Changes

1. **Frontend Image Compression (Browser-side)**
   - I will add a hidden `<input type="file" accept="image/*">` to the preview page.
   - When you select a photo, a small Javascript function will instantly compress and resize it (down to under 1MB) directly inside your browser.
   - This ensures the file is small enough to safely pass through Vercel.

2. **Backend Storage**
   - I will create a new API endpoint `/api/v1/preview/{id}/upload-image`.
   - The compressed image will be converted to a `base64` string and saved directly into your Supabase database.
   - When the post is published, the backend will decode it and upload it to LinkedIn.

> [!WARNING]
> **Video Uploads are not supported in this plan.**
> Vercel Serverless completely blocks files larger than 4.5MB. Video files are much larger than this and cannot be compressed in the browser easily. Furthermore, the LinkedIn API requires a completely different mechanism for video uploads. We will restrict this to **Images Only**.

## User Review Required
Does restricting this to **Images Only** (no video) work for you? If yes, I will build it immediately without needing you to set up any external storage buckets!
