-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "app";

-- CreateEnum
CREATE TYPE "app"."Role" AS ENUM ('USER', 'ADMIN');

-- CreateEnum
CREATE TYPE "app"."ProcessStatus" AS ENUM ('ACTIVE', 'COMPLETED', 'ARCHIVED');

-- CreateEnum
CREATE TYPE "app"."FeedbackType" AS ENUM ('OUTDATED', 'INCORRECT', 'OTHER');

-- CreateEnum
CREATE TYPE "app"."FeedbackStatus" AS ENUM ('OPEN', 'REVIEWING', 'RESOLVED', 'REJECTED');

-- CreateTable
CREATE TABLE "app"."users" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT,
    "email_verified" TIMESTAMP(3),
    "image" TEXT,
    "role" "app"."Role" NOT NULL DEFAULT 'USER',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."accounts" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "provider_account_id" TEXT NOT NULL,
    "refresh_token" TEXT,
    "access_token" TEXT,
    "expires_at" INTEGER,
    "token_type" TEXT,
    "scope" TEXT,
    "id_token" TEXT,
    "session_state" TEXT,

    CONSTRAINT "accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."sessions" (
    "id" TEXT NOT NULL,
    "session_token" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."verification_tokens" (
    "identifier" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "verification_tokens_pkey" PRIMARY KEY ("identifier","token")
);

-- CreateTable
CREATE TABLE "app"."process_types" (
    "id" SERIAL NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "process_types_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."user_processes" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "process_type_id" INTEGER NOT NULL,
    "user_input" TEXT NOT NULL,
    "answers" JSONB,
    "roadmap" JSONB NOT NULL,
    "status" "app"."ProcessStatus" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_processes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."step_progress" (
    "id" TEXT NOT NULL,
    "user_process_id" TEXT NOT NULL,
    "step_order" INTEGER NOT NULL,
    "completed" BOOLEAN NOT NULL DEFAULT false,
    "completed_at" TIMESTAMP(3),

    CONSTRAINT "step_progress_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."feedback" (
    "id" TEXT NOT NULL,
    "user_process_id" TEXT NOT NULL,
    "step_order" INTEGER,
    "type" "app"."FeedbackType" NOT NULL,
    "description" TEXT,
    "status" "app"."FeedbackStatus" NOT NULL DEFAULT 'OPEN',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "feedback_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "app"."users"("email");

-- CreateIndex
CREATE INDEX "accounts_user_id_idx" ON "app"."accounts"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "accounts_provider_provider_account_id_key" ON "app"."accounts"("provider", "provider_account_id");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_session_token_key" ON "app"."sessions"("session_token");

-- CreateIndex
CREATE INDEX "sessions_user_id_idx" ON "app"."sessions"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "process_types_code_key" ON "app"."process_types"("code");

-- CreateIndex
CREATE INDEX "user_processes_user_id_status_idx" ON "app"."user_processes"("user_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "step_progress_user_process_id_step_order_key" ON "app"."step_progress"("user_process_id", "step_order");

-- CreateIndex
CREATE INDEX "feedback_status_created_at_idx" ON "app"."feedback"("status", "created_at");

-- AddForeignKey
ALTER TABLE "app"."accounts" ADD CONSTRAINT "accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."user_processes" ADD CONSTRAINT "user_processes_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."user_processes" ADD CONSTRAINT "user_processes_process_type_id_fkey" FOREIGN KEY ("process_type_id") REFERENCES "app"."process_types"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."step_progress" ADD CONSTRAINT "step_progress_user_process_id_fkey" FOREIGN KEY ("user_process_id") REFERENCES "app"."user_processes"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."feedback" ADD CONSTRAINT "feedback_user_process_id_fkey" FOREIGN KEY ("user_process_id") REFERENCES "app"."user_processes"("id") ON DELETE CASCADE ON UPDATE CASCADE;
