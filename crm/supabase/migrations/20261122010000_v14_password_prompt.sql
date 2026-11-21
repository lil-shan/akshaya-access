alter table job_prompts drop constraint if exists job_prompts_kind_check;
alter table job_prompts add constraint job_prompts_kind_check check (kind in ('otp','captcha_audio','captcha_image','confirm','field','password'));
