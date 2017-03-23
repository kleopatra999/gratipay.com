BEGIN;

    ALTER TABLE emails ADD CONSTRAINT emails_nonce_key UNIQUE (nonce);
    CREATE TABLE claims
    ( nonce         text    NOT NULL REFERENCES emails(nonce)
    , package_id    bigint  NOT NULL REFERENCES packages(id)
    , UNIQUE(nonce, package_id)
     );

END;
