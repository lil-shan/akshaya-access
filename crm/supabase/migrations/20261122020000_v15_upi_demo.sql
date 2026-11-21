alter table payments drop constraint if exists payments_provider_check;
alter table payments add constraint payments_provider_check check (provider in ('simulated_123pay','razorpay_test','eko_uat','upi_qr_demo'));
