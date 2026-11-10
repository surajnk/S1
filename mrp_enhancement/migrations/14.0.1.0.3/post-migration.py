# -*- coding: utf-8 -*-
"""Give every existing Final Yield line one input line.

Plain SQL on purpose: going through the ORM would run the input-line hooks
(roll status, roll remained_qty, parent mirroring) and must not change any
existing data. The parent line already holds the same values, so after this
step parent and child agree. Safe to run twice.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        INSERT INTO final_wo_roll_input (
            sequence, final_roll_id, workorder_id, previous_roll_id,
            previous_roll_quantity, consumed_qty, is_fully_consumed,
            remained_qty, create_uid, create_date, write_uid, write_date
        )
        SELECT 10, f.id, f.workorder_id, f.previous_roll_id,
               COALESCE(f.previous_roll_quantity, 0.0),
               COALESCE(f.consumed_qty, 0.0),
               COALESCE(f.is_fully_consumed, FALSE),
               COALESCE(f.previous_roll_quantity, 0.0) - COALESCE(f.consumed_qty, 0.0),
               COALESCE(f.create_uid, 1), NOW() AT TIME ZONE 'UTC',
               COALESCE(f.write_uid, 1), NOW() AT TIME ZONE 'UTC'
          FROM final_wo_roll f
         WHERE f.previous_roll_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM final_wo_roll_input i WHERE i.final_roll_id = f.id)
    """)
    _logger.info("mrp_enhancement: created %s final roll input lines from "
                 "existing final yield lines", cr.rowcount)
