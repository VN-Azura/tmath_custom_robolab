class MasterSlaveRouter:
    """
    Database router that directs:
    - All writes (INSERT, UPDATE, DELETE) to Master.
    - All reads (SELECT) to Slave.
    """

    TABLES_READ_FROM_MASTER = ['judge_judge', 'judge_submissiontestcase']

    def db_for_read(self, model, **hints):
        """Chỉ đọc từ Slave"""
        if model._meta.db_table in self.TABLES_READ_FROM_MASTER:
            return 'default'
        return 'default'

    def db_for_write(self, model, **hints):
        """Ghi vào Master"""
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Cho phép quan hệ giữa các database"""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Chỉ cho phép migrate trên Master"""
        return db == 'default'
