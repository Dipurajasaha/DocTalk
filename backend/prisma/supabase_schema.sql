-- Supabase SQL script generated from backend/prisma/schema.prisma
-- Paste this into the Supabase SQL editor to create the app tables and enums.

do $$
begin
    create type "Role" as enum ('patient', 'doctor');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type "Gender" as enum ('male', 'female', 'other');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type "AppointmentStatus" as enum (
        'pending',
        'requested',
        'scheduled',
        'completed',
        'cancelled',
        'declined'
    );
exception
    when duplicate_object then null;
end $$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new."updatedAt" = now();
    return new;
end;
$$;

create table if not exists "patients" (
    "username" text primary key,
    "name" text not null,
    "displayName" text,
    "dob" timestamptz(3),
    "gender" "Gender",
    "password" text not null,
    "bloodGroup" text,
    "address" text,
    "mobile" text,
    "email" text,
    "phone" text,
    "profilePic" text,
    "closedDoctorChats" jsonb,
    "doctorChats" jsonb,
    "chatSessions" jsonb,
    "reports" jsonb,
    "medicalImages" jsonb,
    "prescriptions" jsonb,
    "xrayAnalyses" jsonb,
    "customAssets" jsonb,
    "publicKey" text,
    "encryptedPrivateKey" text,
    "createdAt" timestamptz(3) not null default now(),
    "updatedAt" timestamptz(3) not null default now()
);

create table if not exists "doctors" (
    "doctorId" text primary key,
    "name" text not null,
    "displayName" text,
    "gender" "Gender",
    "password" text not null,
    "role" "Role" not null default 'doctor',
    "category" text,
    "location" text,
    "address" text,
    "registrationNumber" text,
    "hospitalName" text,
    "hospitalLocation" text,
    "specialization" text,
    "bio" text,
    "profilePic" text,
    "schedules" jsonb,
    "appointmentRequests" jsonb,
    "payments" jsonb,
    "patientChats" jsonb,
    "assistantChat" jsonb,
    "closedChats" jsonb,
    "publicKey" text,
    "encryptedPrivateKey" text,
    "createdAt" timestamptz(3) not null default now(),
    "updatedAt" timestamptz(3) not null default now()
);

create table if not exists "appointments" (
    "id" text primary key,
    "patientUsername" text not null references "patients" ("username") on delete cascade,
    "doctorId" text not null references "doctors" ("doctorId") on delete cascade,
    "date" text,
    "time" text,
    "scheduledTime" timestamptz(3),
    "reason" text not null,
    "note" text,
    "status" "AppointmentStatus" not null default 'pending',
    "requestedAt" timestamptz(3) not null default now(),
    "createdAt" timestamptz(3) not null default now(),
    "completedAt" timestamptz(3)
);

create index if not exists "appointments_patientUsername_idx"
    on "appointments" ("patientUsername");

create index if not exists "appointments_doctorId_idx"
    on "appointments" ("doctorId");

create index if not exists "appointments_status_idx"
    on "appointments" ("status");

create table if not exists "file_keys" (
    "id" text primary key,
    "fileId" text not null,
    "patientUsername" text references "patients" ("username") on delete cascade,
    "doctorId" text references "doctors" ("doctorId") on delete cascade,
    "encryptedFileKey" text not null,
    "createdAt" timestamptz(3) not null default now()
);

create index if not exists "file_keys_fileId_idx"
    on "file_keys" ("fileId");

create index if not exists "file_keys_patientUsername_idx"
    on "file_keys" ("patientUsername");

create index if not exists "file_keys_doctorId_idx"
    on "file_keys" ("doctorId");

drop trigger if exists set_patients_updated_at on "patients";
create trigger set_patients_updated_at
before update on "patients"
for each row
execute function public.set_updated_at();

drop trigger if exists set_doctors_updated_at on "doctors";
create trigger set_doctors_updated_at
before update on "doctors"
for each row
execute function public.set_updated_at();