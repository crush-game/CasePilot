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
             * @constant
             */
            retrieval_mode: "bm25";
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
             * @constant
             */
            retrieval_mode: "bm25";
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
            /** Occurred At */
            occurred_at?: string | null;
            /** Occurred At Precision */
            occurred_at_precision?: ("minute" | "second") | null;
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
        /**
         * Priority
         * @enum {string}
         */
        Priority: "low" | "normal" | "high" | "urgent";
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
            selected_feedback_ref?: null;
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
        Role: "business" | "knowledge_admin";
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
             * @constant
             */
            retrieval_mode: "bm25";
            /** Score */
            score: number;
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
             * @constant
             */
            retrieval_mode: "bm25";
            /**
             * Data Source
             * @default mock
             * @constant
             */
            data_source: "mock";
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
        /** TicketCreate */
        TicketCreate: {
            /** Feedback Text */
            feedback_text: string;
            /** Customer Email */
            customer_email: string;
            /** Device Ref */
            device_ref?: string | null;
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
