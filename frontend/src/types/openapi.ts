/** Generated from the backend OpenAPI schema. Do not edit manually. */
export interface paths {
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tickets */
        get: operations["list_tickets_api_v1_tickets_get"];
        put?: never;
        /** Create Ticket */
        post: operations["create_ticket_api_v1_tickets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ticket */
        get: operations["get_ticket_api_v1_tickets__ticket_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Ticket */
        patch: operations["update_ticket_api_v1_tickets__ticket_id__patch"];
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Events */
        get: operations["events_api_v1_tickets__ticket_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_v1_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/evidence/{evidence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Log Evidence */
        get: operations["get_log_evidence_api_v1_tickets__ticket_id__evidence__evidence_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/human-tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Human Tasks */
        get: operations["list_human_tasks_api_v1_human_tasks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/human-tasks/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Human Task */
        get: operations["get_human_task_api_v1_human_tasks__task_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/human-tasks/{task_id}/claim": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Claim */
        post: operations["claim_api_v1_human_tasks__task_id__claim_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/human-tasks/{task_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume */
        post: operations["resume_api_v1_human_tasks__task_id__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/takeover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Takeover */
        post: operations["takeover_api_v1_tickets__ticket_id__takeover_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/reinvestigate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reinvestigate */
        post: operations["reinvestigate_api_v1_tickets__ticket_id__reinvestigate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review */
        post: operations["review_api_v1_tickets__ticket_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/close": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Close */
        post: operations["close_api_v1_tickets__ticket_id__close_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/customer-feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Feedback */
        post: operations["feedback_api_v1_tickets__ticket_id__customer_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Experiences */
        get: operations["list_experiences_api_v1_experiences_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiences/{experience_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review Experience */
        post: operations["review_experience_api_v1_experiences__experience_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experience-release-candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Release Candidates */
        get: operations["release_candidates_api_v1_experience_release_candidates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiences/{experience_id}/publications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Release History */
        get: operations["release_history_api_v1_experiences__experience_id__publications_get"];
        put?: never;
        /** Publish */
        post: operations["publish_api_v1_experiences__experience_id__publications_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiences/{experience_id}/publications/{revision}/withdraw": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Withdraw */
        post: operations["withdraw_api_v1_experiences__experience_id__publications__revision__withdraw_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experience-recall": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Recall */
        post: operations["recall_api_v1_experience_recall_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/support/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Conversations */
        get: operations["conversations_api_v1_support_conversations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/support/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Conversation */
        get: operations["conversation_api_v1_support_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/support/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Turn */
        post: operations["turn_api_v1_support_turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/channels/mock/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mock Event */
        post: operations["mock_event_api_v1_channels_mock_events_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/channels/deliveries/{delivery_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Delivery */
        get: operations["delivery_api_v1_channels_deliveries__delivery_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/support-replies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Support Replies */
        get: operations["support_replies_api_v1_tickets__ticket_id__support_replies_get"];
        put?: never;
        /** Support Reply */
        post: operations["support_reply_api_v1_tickets__ticket_id__support_replies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tickets/{ticket_id}/support-conversation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Support Conversation */
        get: operations["support_conversation_api_v1_tickets__ticket_id__support_conversation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Documents */
        get: operations["list_documents_api_v1_knowledge_documents_get"];
        put?: never;
        /** Upload Document */
        post: operations["upload_document_api_v1_knowledge_documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Document */
        get: operations["get_document_api_v1_knowledge_documents__document_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/documents/{document_id}/source": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source */
        get: operations["source_api_v1_knowledge_documents__document_id__source_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/documents/{document_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Archive */
        post: operations["archive_api_v1_knowledge_documents__document_id__archive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Jobs */
        get: operations["list_jobs_api_v1_knowledge_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_api_v1_knowledge_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/jobs/{job_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_api_v1_knowledge_jobs__job_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search */
        post: operations["search_api_v1_knowledge_search_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge/chunks/{chunk_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Citation */
        get: operations["citation_api_v1_knowledge_chunks__chunk_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/assessments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Assessments */
        get: operations["assessments_api_v1_quality_assessments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/assessments/{assessment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Assessment */
        get: operations["assessment_api_v1_quality_assessments__assessment_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/assessments/{assessment_id}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Decision */
        post: operations["decision_api_v1_quality_assessments__assessment_id__decision_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Batch */
        post: operations["create_batch_api_v1_quality_batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Rules */
        get: operations["rules_api_v1_quality_rules_get"];
        put?: never;
        /** Publish Rules */
        post: operations["publish_rules_api_v1_quality_rules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/weekly": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Reports */
        get: operations["list_reports_api_v1_reports_weekly_get"];
        put?: never;
        /** Generate */
        post: operations["generate_api_v1_reports_weekly_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/weekly/{report_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["detail_api_v1_reports_weekly__report_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/weekly/{report_id}/delivery": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Enqueue */
        post: operations["enqueue_api_v1_reports_weekly__report_id__delivery_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/quality/assessments/{assessment_id}/knowledge-gap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Gap */
        post: operations["submit_gap_api_v1_quality_assessments__assessment_id__knowledge_gap_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge-gaps": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Gaps */
        get: operations["list_gaps_api_v1_knowledge_gaps_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge-gaps/{gap_id}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Gap */
        post: operations["resolve_gap_api_v1_knowledge_gaps__gap_id__decision_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActionResult */
        ActionResult: {
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            status: components["schemas"]["TicketStatus"];
            /** Version */
            version: number;
            /** Run Id */
            run_id?: string | null;
            /** Human Task Id */
            human_task_id?: string | null;
        };
        /** Body_upload_document_api_v1_knowledge_documents_post */
        Body_upload_document_api_v1_knowledge_documents_post: {
            /** File */
            file: string;
            /** Metadata */
            metadata: string;
        };
        /** ChannelAccepted */
        ChannelAccepted: {
            /**
             * Event Id
             * Format: uuid
             */
            event_id: string;
            /**
             * Disposition
             * @enum {string}
             */
            disposition: "processed" | "historical" | "edited" | "closed";
            /** Delivery Id */
            delivery_id?: string | null;
            /** Ticket No */
            ticket_no?: string | null;
        };
        /** Citation */
        Citation: {
            /** Ref */
            ref: string;
            /**
             * Chunk Id
             * Format: uuid
             */
            chunk_id: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Doc Key */
            doc_key: string;
            /** Document Version */
            document_version: number;
            /** Document Status */
            document_status: string;
            /** Title */
            title: string;
            /** Filename */
            filename: string;
            /** Source Type */
            source_type: string;
            /** Source Checksum */
            source_checksum: string;
            /** Content Hash */
            content_hash: string;
            /** Text */
            text: string;
            /** Heading Path */
            heading_path: string[];
            /** Start Line */
            start_line: number;
            /** End Line */
            end_line: number;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Product Scope */
            product_scope: string[];
            /** Firmware Versions */
            firmware_versions: string[];
            /** Regions */
            regions: string[];
            /** Channels */
            channels: string[];
            /** Effective From */
            effective_from: string | null;
            /** Effective To */
            effective_to: string | null;
            /** Usable */
            usable: boolean;
            /** Missing Fields */
            missing_fields: string[];
            /** Unavailable Reasons */
            unavailable_reasons: string[];
            /**
             * Data Source
             * @default mock
             * @constant
             */
            data_source: "mock";
            /**
             * Retrieval Mode
             * @default bm25
             * @enum {string}
             */
            retrieval_mode: "bm25" | "hybrid";
        };
        /** CloseInput */
        CloseInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "resolved" | "unresolved";
            /** Verified Steps */
            verified_steps?: string | null;
        };
        /** DeductionCount */
        DeductionCount: {
            /**
             * Rule Id
             * @enum {string}
             */
            rule_id: "fatal_review" | "business_incomplete" | "process_late" | "format_missing" | "service_dismissive" | "operation_model";
            /** Label */
            label: string;
            /** Count */
            count: number;
        };
        /** DeliveryView */
        DeliveryView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Channel
             * @enum {string}
             */
            channel: "app" | "mock";
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "delivered" | "failed";
            /** Attempts */
            attempts: number;
            /** Text */
            text: string;
            /** Last Error */
            last_error: string | null;
            /** Provider Ref */
            provider_ref: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** DocumentActionResult */
        DocumentActionResult: {
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Revision */
            revision: number;
            /** Status */
            status: string;
        };
        /** DocumentList */
        DocumentList: {
            /** Items */
            items: components["schemas"]["DocumentView"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Has More */
            has_more: boolean;
        };
        /** DocumentView */
        DocumentView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Doc Key */
            doc_key: string;
            /** Version */
            version: number;
            /** Revision */
            revision: number;
            /** Title */
            title: string;
            /** Filename */
            filename: string;
            /** Source Type */
            source_type: string;
            /**
             * Data Source
             * @constant
             */
            data_source: "mock";
            /**
             * Retrieval Mode
             * @enum {string}
             */
            retrieval_mode: "bm25" | "hybrid";
            /** Product Scope */
            product_scope: string[];
            /** Firmware Versions */
            firmware_versions: string[];
            /** Regions */
            regions: string[];
            /** Channels */
            channels: string[];
            /** Effective From */
            effective_from: string | null;
            /** Effective To */
            effective_to: string | null;
            /** Status */
            status: string;
            /** Checksum */
            checksum: string;
            /** Index Version */
            index_version: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** EventList */
        EventList: {
            /** Items */
            items: components["schemas"]["EventView"][];
            /** Next After Id */
            next_after_id: number;
            /** Has More */
            has_more: boolean;
        };
        /** EventView */
        EventView: {
            /** Id */
            id: number;
            /** Run Id */
            run_id: string | null;
            /** Event Type */
            event_type: string;
            /** Payload Json */
            payload_json: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ExperienceContent */
        ExperienceContent: {
            /** Problem */
            problem: string;
            /** Conditions */
            conditions: {
                [key: string]: string;
            };
            /** Result Note */
            result_note: string;
            /** Verified Steps */
            verified_steps: string;
            /**
             * Confirmation
             * @enum {string}
             */
            confirmation: "human_verified" | "customer_confirmed";
            /**
             * Data Source
             * @constant
             */
            data_source: "mock";
            /** Evidence Refs */
            evidence_refs: string[];
            /** Limitations */
            limitations: string[];
        };
        /** ExperienceHint */
        ExperienceHint: {
            /**
             * Publication Id
             * Format: uuid
             */
            publication_id: string;
            /** Revision */
            revision: number;
            /**
             * Source Ticket Id
             * Format: uuid
             */
            source_ticket_id: string;
            /** Problem */
            problem: string;
            /** Verified Steps */
            verified_steps: string;
            /** Conditions */
            conditions: {
                [key: string]: string;
            };
            /**
             * Source Type
             * @default verified_case
             * @constant
             */
            source_type: "verified_case";
        };
        /** ExperienceList */
        ExperienceList: {
            /** Items */
            items: components["schemas"]["ExperienceView"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** ExperienceReviewInput */
        ExperienceReviewInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            /**
             * Decision
             * @enum {string}
             */
            decision: "review" | "archive";
        };
        /** ExperienceView */
        ExperienceView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Source Ticket Id
             * Format: uuid
             */
            source_ticket_id: string;
            /** Source Run Id */
            source_run_id: string | null;
            /**
             * Source Action Id
             * Format: uuid
             */
            source_action_id: string;
            /** Result Version */
            result_version: number;
            /** Version */
            version: number;
            /**
             * Status
             * @enum {string}
             */
            status: "candidate" | "reviewed" | "archived";
            content_json: components["schemas"]["ExperienceContent"];
            /** Review Json */
            review_json: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** FactView */
        FactView: {
            /** Field */
            field: string;
            /** Value Json */
            value_json: {
                [key: string]: unknown;
            };
            /** Source Type */
            source_type: string;
            /** Fact Version */
            fact_version: number;
        };
        /** FactsPatch */
        FactsPatch: {
            /** Device Ref */
            device_ref?: string | null;
            /** Platform */
            platform?: ("android" | "ios") | null;
            /** App Version */
            app_version?: string | null;
            /** Product Ref */
            product_ref?: string | null;
            /** Firmware Version */
            firmware_version?: string | null;
            /** Region */
            region?: string | null;
            /** Channel */
            channel?: string | null;
            /** Occurred At */
            occurred_at?: string | null;
            /** Occurred At Precision */
            occurred_at_precision?: ("minute" | "second") | null;
        };
        /** FaultCounts */
        FaultCounts: {
            /** Wifi */
            wifi: number;
            /** Other */
            other: number;
        };
        /** FeedbackInput */
        FeedbackInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "contacted" | "resolved" | "unresolved";
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HandoffOffer */
        HandoffOffer: {
            /** Question */
            question: string;
            /** Product Ref */
            product_ref?: string | null;
            /** Firmware Version */
            firmware_version?: string | null;
            /** Missing Fields */
            missing_fields: ("product_ref" | "firmware_version")[];
        };
        /** HumanTaskList */
        HumanTaskList: {
            /** Items */
            items: components["schemas"]["HumanTaskView"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * HumanTaskStatus
         * @enum {string}
         */
        HumanTaskStatus: "unclaimed" | "claimed" | "resuming" | "completed" | "cancelled";
        /** HumanTaskView */
        HumanTaskView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /** Pause Key */
            pause_key: string;
            /** Reason Code */
            reason_code: string;
            status: components["schemas"]["HumanTaskStatus"];
            /** Assignee Id */
            assignee_id: string | null;
            /** Payload Json */
            payload_json: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Expected Version */
            expected_version: number;
            priority: components["schemas"]["Priority"];
        };
        /** IngestionCreated */
        IngestionCreated: {
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** Already Exists */
            already_exists: boolean;
        };
        /** JobActionResult */
        JobActionResult: {
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** Revision */
            revision: number;
            /** Status */
            status: string;
        };
        /** JobList */
        JobList: {
            /** Items */
            items: components["schemas"]["JobView"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Has More */
            has_more: boolean;
        };
        /** JobView */
        JobView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Status */
            status: string;
            /** Stage */
            stage: string;
            /** Attempt */
            attempt: number;
            /** Revision */
            revision: number;
            /** Error Code */
            error_code: string | null;
            /** Retryable */
            retryable: boolean;
            /** Index Version */
            index_version: number | null;
            /** History Json */
            history_json: {
                [key: string]: unknown;
            }[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** KnowledgeAction */
        KnowledgeAction: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Revision */
            expected_revision: number;
            /** Reason */
            reason: string;
        };
        /** KnowledgeGapDecision */
        KnowledgeGapDecision: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "confirmed" | "dismissed";
            /** Reason */
            reason: string;
        };
        /** KnowledgeGapInput */
        KnowledgeGapInput: {
            /**
             * Rule Id
             * @enum {string}
             */
            rule_id: "fatal_review" | "business_incomplete" | "process_late" | "format_missing" | "service_dismissive" | "operation_model";
            /** Statement */
            statement: string;
        };
        /** KnowledgeGapView */
        KnowledgeGapView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Assessment Id
             * Format: uuid
             */
            assessment_id: string;
            /**
             * Rule Id
             * @enum {string}
             */
            rule_id: "fatal_review" | "business_incomplete" | "process_late" | "format_missing" | "service_dismissive" | "operation_model";
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "confirmed" | "dismissed";
            /** Evidence Json */
            evidence_json: {
                [key: string]: unknown;
            };
            /** Resolution Json */
            resolution_json: {
                [key: string]: unknown;
            };
        };
        /** LogEvidenceView */
        LogEvidenceView: {
            /** Ref */
            ref: string;
            /** Title */
            title: string;
            /** Text */
            text: string;
            /**
             * Data Source
             * @constant
             */
            data_source: "mock";
            /**
             * Source Type
             * @enum {string}
             */
            source_type: "detailed_log" | "telemetry";
            /** Domain */
            domain: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Start Line */
            start_line: number;
            /** End Line */
            end_line: number;
            /** Usable */
            usable: boolean;
            /** Content Hash */
            content_hash: string;
            /** Source Checksum */
            source_checksum: string;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Product Scope */
            product_scope: string[];
            /** Firmware Versions */
            firmware_versions: string[];
        };
        /** LoginInput */
        LoginInput: {
            /** Login */
            login: string;
            /**
             * Password
             * Format: password
             */
            password: string;
        };
        /** LoginResult */
        LoginResult: {
            user: components["schemas"]["UserView"];
            /** Csrf Token */
            csrf_token: string;
        };
        /** MetricRatio */
        MetricRatio: {
            /** Count */
            count: number;
            /** Total */
            total: number;
        };
        /** MockEvent */
        MockEvent: {
            /**
             * Event Id
             * Format: uuid
             */
            event_id: string;
            /**
             * Sender Id
             * Format: uuid
             */
            sender_id: string;
            /** Conversation Ref */
            conversation_ref: string;
            /** Issue Ref */
            issue_ref: string;
            /** Reply Target */
            reply_target: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Sequence */
            sequence: number;
            /**
             * Kind
             * @default message
             * @enum {string}
             */
            kind: "message" | "edit";
            /**
             * Action
             * @default message
             * @enum {string}
             */
            action: "message" | "handoff";
            /** Text */
            text: string;
            /**
             * Simulated Failures
             * @default 0
             */
            simulated_failures: number;
        };
        /**
         * Priority
         * @enum {string}
         */
        Priority: "low" | "normal" | "high" | "urgent";
        /** PublicationCommand */
        PublicationCommand: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Reason */
            reason: string;
        };
        /** PublicationView */
        PublicationView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Experience Id
             * Format: uuid
             */
            experience_id: string;
            /** Revision */
            revision: number;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "withdrawn";
            /** Conditions */
            conditions: {
                [key: string]: string;
            };
            /** Note */
            note: string;
            /** Withdrawal Note */
            withdrawal_note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** QualityBatchInput */
        QualityBatchInput: {
            /** Batch Key */
            batch_key: string;
            /**
             * Random Pct
             * @default 10
             */
            random_pct: number;
            /**
             * Max Calls
             * @default 20
             */
            max_calls: number;
            /** Ticket Id */
            ticket_id?: string | null;
        };
        /** QualityBatchView */
        QualityBatchView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Batch Key */
            batch_key: string;
            /** Ticket Id */
            ticket_id?: string | null;
            /** Random Pct */
            random_pct: number;
            /** Max Calls */
            max_calls: number;
            /** Calls Used */
            calls_used: number;
            /** Selection Json */
            selection_json: {
                [key: string]: unknown;
            }[];
        };
        /** QualityCoverage */
        QualityCoverage: {
            /** Total */
            total: number;
            /** Insufficient */
            insufficient: number;
            /** Screened */
            screened: number;
            /** Ai Checked */
            ai_checked: number;
            /** Reviewed */
            reviewed: number;
        };
        /** QualityDecision */
        QualityDecision: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /**
             * Decision
             * @enum {string}
             */
            decision: "confirm" | "adjust" | "appeal" | "rescore";
            /** Reason */
            reason: string;
            /** Findings */
            findings?: components["schemas"]["QualityFinding"][] | null;
            /** Rule Version */
            rule_version?: string | null;
        };
        /** QualityDetail */
        QualityDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Snapshot Id
             * Format: uuid
             */
            snapshot_id: string;
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            /**
             * Subject Id
             * Format: uuid
             */
            subject_id: string;
            /** Subject Name */
            subject_name: string;
            /** Rule Version */
            rule_version: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "screened" | "ai_queued" | "pending_review" | "finalized" | "appealed" | "insufficient";
            /** Version */
            version: number;
            /** Result Json */
            result_json: {
                [key: string]: unknown;
            };
            /** History Json */
            history_json: {
                [key: string]: unknown;
            }[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Snapshot */
            snapshot: {
                [key: string]: unknown;
            };
        };
        /** QualityFinding */
        QualityFinding: {
            /**
             * Rule Id
             * @enum {string}
             */
            rule_id: "fatal_review" | "business_incomplete" | "process_late" | "format_missing" | "service_dismissive" | "operation_model";
            /** Evidence */
            evidence: string[];
        };
        /** QualityList */
        QualityList: {
            /** Items */
            items: components["schemas"]["QualityView"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Snapshot Missing */
            snapshot_missing: string[];
        };
        /** QualityRuleSetInput */
        QualityRuleSetInput: {
            /** Version */
            version: string;
            /** Deductions */
            deductions: {
                [key: string]: number;
            };
            /** Caps */
            caps: {
                [key: string]: number;
            };
            /** Follow Up Minutes */
            follow_up_minutes: number;
            /**
             * Require Greeting
             * @default false
             */
            require_greeting: boolean;
        };
        /** QualityView */
        QualityView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Snapshot Id
             * Format: uuid
             */
            snapshot_id: string;
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            /**
             * Subject Id
             * Format: uuid
             */
            subject_id: string;
            /** Subject Name */
            subject_name: string;
            /** Rule Version */
            rule_version: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "screened" | "ai_queued" | "pending_review" | "finalized" | "appealed" | "insufficient";
            /** Version */
            version: number;
            /** Result Json */
            result_json: {
                [key: string]: unknown;
            };
            /** History Json */
            history_json: {
                [key: string]: unknown;
            }[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ReasonAction */
        ReasonAction: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
        };
        /** RecallQuery */
        RecallQuery: {
            /** Query */
            query: string;
            /** Product Ref */
            product_ref: string;
            /** Firmware Version */
            firmware_version: string;
            /** Platform */
            platform?: ("android" | "ios") | null;
            /** App Version */
            app_version?: string | null;
            /** Region */
            region?: string | null;
            /** Channel */
            channel?: string | null;
        };
        /** ReinvestigateInput */
        ReinvestigateInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            facts_patch?: components["schemas"]["FactsPatch"];
        };
        /** ReportRequest */
        ReportRequest: {
            /** Week Start */
            week_start?: string | null;
        };
        /** ResumeInput */
        ResumeInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            facts_patch?: components["schemas"]["FactsPatch"];
            /** Selected Feedback Ref */
            selected_feedback_ref?: string | null;
        };
        /** ReviewInput */
        ReviewInput: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /**
             * Decision
             * @enum {string}
             */
            decision: "approve" | "revise";
            /** Reply Draft */
            reply_draft?: string | null;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "business" | "knowledge_admin" | "consumer";
        /**
         * RunStatus
         * @enum {string}
         */
        RunStatus: "queued" | "running" | "paused" | "succeeded" | "failed" | "superseded";
        /** RunView */
        RunView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            /** Graph Version */
            graph_version: string;
            /** Case Version */
            case_version: number;
            status: components["schemas"]["RunStatus"];
            /** Budget Json */
            budget_json: {
                [key: string]: unknown;
            };
            /** Stop Reason */
            stop_reason: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Checkpoint Ref */
            checkpoint_ref?: {
                [key: string]: unknown;
            } | null;
            /**
             * Cancel Requested
             * @default false
             */
            cancel_requested: boolean;
            /** Nodes */
            nodes?: {
                [key: string]: unknown;
            }[];
        };
        /** SearchHit */
        SearchHit: {
            /** Ref */
            ref: string;
            /**
             * Chunk Id
             * Format: uuid
             */
            chunk_id: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Doc Key */
            doc_key: string;
            /** Document Version */
            document_version: number;
            /** Document Status */
            document_status: string;
            /** Title */
            title: string;
            /** Filename */
            filename: string;
            /** Source Type */
            source_type: string;
            /** Source Checksum */
            source_checksum: string;
            /** Content Hash */
            content_hash: string;
            /** Text */
            text: string;
            /** Heading Path */
            heading_path: string[];
            /** Start Line */
            start_line: number;
            /** End Line */
            end_line: number;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Product Scope */
            product_scope: string[];
            /** Firmware Versions */
            firmware_versions: string[];
            /** Regions */
            regions: string[];
            /** Channels */
            channels: string[];
            /** Effective From */
            effective_from: string | null;
            /** Effective To */
            effective_to: string | null;
            /** Usable */
            usable: boolean;
            /** Missing Fields */
            missing_fields: string[];
            /** Unavailable Reasons */
            unavailable_reasons: string[];
            /**
             * Data Source
             * @default mock
             * @constant
             */
            data_source: "mock";
            /**
             * Retrieval Mode
             * @default bm25
             * @enum {string}
             */
            retrieval_mode: "bm25" | "hybrid";
            /** Score */
            score: number;
            /** Rerank Score */
            rerank_score: number | null;
        };
        /** SearchQuery */
        SearchQuery: {
            /** Product Ref */
            product_ref?: string | null;
            /** Firmware Version */
            firmware_version?: string | null;
            /** Region */
            region?: string | null;
            /** Channel */
            channel?: string | null;
            /** As Of */
            as_of?: string | null;
            /** Query */
            query: string;
            /**
             * Limit
             * @default 20
             */
            limit: number;
            /** Retrieval Mode */
            retrieval_mode?: ("bm25" | "hybrid") | null;
            /**
             * Rerank
             * @default false
             */
            rerank: boolean;
        };
        /** SearchResult */
        SearchResult: {
            /** Hits */
            hits: components["schemas"]["SearchHit"][];
            /** Missing Fields */
            missing_fields: string[];
            /** Index Version */
            index_version: number;
            /** Tokenizer */
            tokenizer: string;
            /**
             * Retrieval Mode
             * @default bm25
             * @enum {string}
             */
            retrieval_mode: "bm25" | "hybrid";
            /**
             * Data Source
             * @default mock
             * @constant
             */
            data_source: "mock";
            /** Embedding Profile Id */
            embedding_profile_id: string | null;
            /**
             * Inference Mode
             * @default none
             * @enum {string}
             */
            inference_mode: "none" | "contract" | "real";
            /**
             * Rerank Mode
             * @default off
             * @enum {string}
             */
            rerank_mode: "off" | "contract" | "real";
            /** Provider Usage */
            provider_usage: {
                [key: string]: unknown;
            }[];
            /** Retrieval Details */
            retrieval_details: {
                [key: string]: unknown;
            };
        };
        /** SourceView */
        SourceView: {
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Filename */
            filename: string;
            /** Source Checksum */
            source_checksum: string;
            /** Text */
            text: string;
            /**
             * Redacted
             * @default true
             * @constant
             */
            redacted: true;
        };
        /** SupportAccepted */
        SupportAccepted: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Ticket No */
            ticket_no?: string | null;
            ticket_status?: components["schemas"]["TicketStatus"] | null;
            /**
             * Flow Version
             * @default support-v1
             * @enum {string}
             */
            flow_version: "support-v1" | "support-v2";
            turn: components["schemas"]["SupportTurnView"];
        };
        /** SupportAgentReply */
        SupportAgentReply: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            /** Text */
            text: string;
        };
        /** SupportConversationView */
        SupportConversationView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Ticket No */
            ticket_no?: string | null;
            ticket_status?: components["schemas"]["TicketStatus"] | null;
            /**
             * Flow Version
             * @default support-v1
             * @enum {string}
             */
            flow_version: "support-v1" | "support-v2";
        };
        /** SupportDetail */
        SupportDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Ticket No */
            ticket_no?: string | null;
            ticket_status?: components["schemas"]["TicketStatus"] | null;
            /**
             * Flow Version
             * @default support-v1
             * @enum {string}
             */
            flow_version: "support-v1" | "support-v2";
            /** Turns */
            turns: components["schemas"]["SupportTurnView"][];
        };
        /** SupportMessage */
        SupportMessage: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Conversation Id */
            conversation_id?: string | null;
            /**
             * Action
             * @default message
             * @enum {string}
             */
            action: "message" | "clarify" | "handoff" | "solved" | "submit_fault";
            /**
             * Text
             * @default
             */
            text: string;
            /** Product Ref */
            product_ref?: string | null;
            /** Firmware Version */
            firmware_version?: string | null;
            /** Flow Version */
            flow_version?: ("support-v1" | "support-v2") | null;
            /** Device Ref */
            device_ref?: string | null;
            /** Platform */
            platform?: ("android" | "ios") | null;
            /** App Version */
            app_version?: string | null;
            /** Occurred At */
            occurred_at?: string | null;
        };
        /** SupportReply */
        SupportReply: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "answer" | "clarify" | "handoff_offer" | "handoff" | "received" | "feedback" | "agent_reply" | "investigation_queued";
            /** Text */
            text: string;
            /** Evidence Ref */
            evidence_ref?: string | null;
            /** Evidence Title */
            evidence_title?: string | null;
            /** Service Window */
            service_window?: string | null;
            offer?: components["schemas"]["HandoffOffer"] | null;
        };
        /** SupportTurnView */
        SupportTurnView: {
            /** Id */
            id: number;
            /** Request Text */
            request_text: string;
            reply_json: components["schemas"]["SupportReply"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** TicketCreate */
        TicketCreate: {
            /** Feedback Text */
            feedback_text: string;
            /** Customer Email */
            customer_email: string;
            /** Device Ref */
            device_ref?: string | null;
            /** Platform */
            platform?: ("android" | "ios") | null;
            /** App Version */
            app_version?: string | null;
            /** Product Ref */
            product_ref?: string | null;
            /** Firmware Version */
            firmware_version?: string | null;
            /** Region */
            region?: string | null;
            /** Channel */
            channel?: string | null;
            /** Occurred At */
            occurred_at?: string | null;
            /** Occurred At Precision */
            occurred_at_precision?: ("minute" | "second") | null;
            /** @default normal */
            priority: components["schemas"]["Priority"];
            /** Artifact Ids */
            artifact_ids?: string[];
        };
        /** TicketCreated */
        TicketCreated: {
            /**
             * Ticket Id
             * Format: uuid
             */
            ticket_id: string;
            /** Ticket No */
            ticket_no: string;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Version */
            version: number;
            status: components["schemas"]["TicketStatus"];
        };
        /** TicketDetail */
        TicketDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ticket No */
            ticket_no: string;
            /** Source */
            source: string;
            /**
             * Data Source
             * @constant
             */
            data_source: "mock";
            /** Customer Email */
            customer_email: string;
            /** Feedback Text */
            feedback_text: string;
            /** Device Ref */
            device_ref: string | null;
            /** Occurred At */
            occurred_at: string | null;
            /** Occurred At Original */
            occurred_at_original: string | null;
            /** Occurred At Precision */
            occurred_at_precision: string | null;
            status: components["schemas"]["TicketStatus"];
            priority: components["schemas"]["Priority"];
            /** Assignee Id */
            assignee_id: string | null;
            /** Version */
            version: number;
            /** Active Run Id */
            active_run_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Latest Event Id */
            latest_event_id: number;
            /** Solution Json */
            solution_json: {
                [key: string]: unknown;
            };
            /** Result Json */
            result_json: {
                [key: string]: unknown;
            };
            /** Human Task Id */
            human_task_id: string | null;
            /**
             * Cancel Requested
             * @default false
             */
            cancel_requested: boolean;
            /** Latest Run Id */
            latest_run_id: string | null;
            /** Facts */
            facts: components["schemas"]["FactView"][];
        };
        /** TicketList */
        TicketList: {
            /** Items */
            items: components["schemas"]["TicketView"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** TicketPatch */
        TicketPatch: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
            priority?: components["schemas"]["Priority"] | null;
            /** Assignee Id */
            assignee_id?: string | null;
        };
        /**
         * TicketStatus
         * @enum {string}
         */
        TicketStatus: "QUEUED" | "RUNNING" | "WAITING_HUMAN" | "WAITING_CUSTOMER" | "PENDING_CONFIRMATION" | "RESOLVED" | "CLOSED_UNRESOLVED";
        /** TicketView */
        TicketView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ticket No */
            ticket_no: string;
            /** Source */
            source: string;
            /**
             * Data Source
             * @constant
             */
            data_source: "mock";
            /** Customer Email */
            customer_email: string;
            /** Feedback Text */
            feedback_text: string;
            /** Device Ref */
            device_ref: string | null;
            /** Occurred At */
            occurred_at: string | null;
            /** Occurred At Original */
            occurred_at_original: string | null;
            /** Occurred At Precision */
            occurred_at_precision: string | null;
            status: components["schemas"]["TicketStatus"];
            priority: components["schemas"]["Priority"];
            /** Assignee Id */
            assignee_id: string | null;
            /** Version */
            version: number;
            /** Active Run Id */
            active_run_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** UserView */
        UserView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Login */
            login: string;
            role: components["schemas"]["Role"];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** VersionedAction */
        VersionedAction: {
            /**
             * Action Id
             * Format: uuid
             */
            action_id: string;
            /** Expected Version */
            expected_version: number;
        };
        /** WeeklyDeliveryView */
        WeeklyDeliveryView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Report Id
             * Format: uuid
             */
            report_id: string;
            /** Group Key */
            group_key: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "mock" | "feishu";
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "sending" | "sent" | "failed" | "unknown";
            /** Attempts */
            attempts: number;
            /** Receipt */
            receipt: string | null;
        };
        /** WeeklyMetrics */
        WeeklyMetrics: {
            /** Conversations */
            conversations: number;
            self_resolved: components["schemas"]["MetricRatio"];
            handoff: components["schemas"]["MetricRatio"];
            /** New Tickets */
            new_tickets: number;
            /** Pending Human At Cutoff */
            pending_human_at_cutoff: number;
            faults: components["schemas"]["FaultCounts"];
            quality: components["schemas"]["QualityCoverage"];
            /** Deductions */
            deductions: components["schemas"]["DeductionCount"][];
        };
        /** WeeklyReportView */
        WeeklyReportView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /** Revision */
            revision: number;
            /** Definition Version */
            definition_version: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            metrics_json: components["schemas"]["WeeklyMetrics"];
            /** Deliveries */
            deliveries: components["schemas"]["WeeklyDeliveryView"][];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserView"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_tickets_api_v1_tickets_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                status?: components["schemas"]["TicketStatus"] | null;
                priority?: components["schemas"]["Priority"] | null;
                assignee_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_ticket_api_v1_tickets_post: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TicketCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ticket_api_v1_tickets__ticket_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_ticket_api_v1_tickets__ticket_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TicketPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    events_api_v1_tickets__ticket_id__events_get: {
        parameters: {
            query?: {
                after_id?: number;
                limit?: number;
            };
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EventList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_v1_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_log_evidence_api_v1_tickets__ticket_id__evidence__evidence_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
                evidence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LogEvidenceView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_human_tasks_api_v1_human_tasks_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["HumanTaskStatus"] | null;
                assignee_id?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HumanTaskList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_human_task_api_v1_human_tasks__task_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HumanTaskView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    claim_api_v1_human_tasks__task_id__claim_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionedAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_api_v1_human_tasks__task_id__resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    takeover_api_v1_tickets__ticket_id__takeover_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReasonAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reinvestigate_api_v1_tickets__ticket_id__reinvestigate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReinvestigateInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_api_v1_tickets__ticket_id__review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    close_api_v1_tickets__ticket_id__close_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CloseInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    feedback_api_v1_tickets__ticket_id__customer_feedback_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_experiences_api_v1_experiences_get: {
        parameters: {
            query?: {
                status?: ("candidate" | "reviewed" | "archived") | null;
                ticket_id?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExperienceList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_experience_api_v1_experiences__experience_id__review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experience_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExperienceReviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExperienceView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    release_candidates_api_v1_experience_release_candidates_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExperienceView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    release_history_api_v1_experiences__experience_id__publications_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experience_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicationView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_api_v1_experiences__experience_id__publications_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experience_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_api_v1_experiences__experience_id__publications__revision__withdraw_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experience_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    recall_api_v1_experience_recall_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecallQuery"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExperienceHint"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    conversations_api_v1_support_conversations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupportConversationView"][];
                };
            };
        };
    };
    conversation_api_v1_support_conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupportDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    turn_api_v1_support_turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SupportMessage"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupportAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mock_event_api_v1_channels_mock_events_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MockEvent"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChannelAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delivery_api_v1_channels_deliveries__delivery_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                delivery_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    support_replies_api_v1_tickets__ticket_id__support_replies_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    support_reply_api_v1_tickets__ticket_id__support_replies_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SupportAgentReply"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    support_conversation_api_v1_tickets__ticket_id__support_conversation_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ticket_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupportDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_documents_api_v1_knowledge_documents_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                status?: ("pending" | "active" | "failed" | "archived" | "superseded") | null;
                doc_key?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_document_api_v1_knowledge_documents_post: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_document_api_v1_knowledge_documents_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestionCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_document_api_v1_knowledge_documents__document_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_api_v1_knowledge_documents__document_id__source_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_api_v1_knowledge_documents__document_id__archive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgeAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_jobs_api_v1_knowledge_jobs_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                status?: ("queued" | "running" | "succeeded" | "failed" | "cancelled") | null;
                document_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_job_api_v1_knowledge_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_api_v1_knowledge_jobs__job_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgeAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_api_v1_knowledge_search_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchQuery"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    citation_api_v1_knowledge_chunks__chunk_id__get: {
        parameters: {
            query?: {
                product_ref?: string | null;
                firmware_version?: string | null;
                region?: string | null;
                channel?: string | null;
                as_of?: string | null;
            };
            header?: never;
            path: {
                chunk_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Citation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assessments_api_v1_quality_assessments_get: {
        parameters: {
            query?: {
                ticket_id?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assessment_api_v1_quality_assessments__assessment_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                assessment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decision_api_v1_quality_assessments__assessment_id__decision_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                assessment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QualityDecision"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_batch_api_v1_quality_batches_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QualityBatchInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityBatchView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rules_api_v1_quality_rules_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityRuleSetInput"][];
                };
            };
        };
    };
    publish_rules_api_v1_quality_rules_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QualityRuleSetInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QualityRuleSetInput"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reports_api_v1_reports_weekly_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeeklyReportView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_api_v1_reports_weekly_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeeklyReportView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    detail_api_v1_reports_weekly__report_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                report_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeeklyReportView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enqueue_api_v1_reports_weekly__report_id__delivery_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                report_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeeklyDeliveryView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_gap_api_v1_quality_assessments__assessment_id__knowledge_gap_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                assessment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgeGapInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeGapView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_gaps_api_v1_knowledge_gaps_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeGapView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_gap_api_v1_knowledge_gaps__gap_id__decision_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gap_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgeGapDecision"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeGapView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    live_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
