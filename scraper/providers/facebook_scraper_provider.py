# في fetch_jobs
for post in get_posts(
    group_id, 
    group=True, 
    pages=max_pages, 
    cookies=self.cookies_file,
    extra_info=False  # عشان يسرع
):
