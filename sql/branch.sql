BEGIN;

    ALTER TABLE emails ADD CONSTRAINT emails_nonce_key UNIQUE (nonce);
    CREATE TABLE claims
    ( nonce         text    NOT NULL REFERENCES emails(nonce)   ON DELETE CASCADE
                                                                ON UPDATE RESTRICT
    , package_id    bigint  NOT NULL REFERENCES packages(id)    ON DELETE RESTRICT
                                                                ON UPDATE RESTRICT
    , UNIQUE(nonce, package_id)
     );

END;
